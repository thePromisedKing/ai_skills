#!/usr/bin/env python3
"""Work-tracker adapters for the ai-skills suite.

One command surface over Jira, Odoo, GitHub Issues, local Markdown files, and
`none`. Configuration comes from .ai-skills/config.yml; credentials come only
from the environment variables that file names, never from arguments.

Output is JSON on stdout. Diagnostics go to stderr. Exit codes:
    0  success
    2  usage error
    3  UNSUPPORTED for the configured adapter
    4  credentials absent or invalid
    5  remote or transport error

Standard library only. PyYAML is used when importable; otherwise a small parser
covers the configuration subset the suite's own template uses.
"""

from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

TIMEOUT_SECONDS = 30  # A tracker read that takes longer than this is a fault,
                      # not slowness worth waiting through inside a workflow.


# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------

class ToolError(Exception):
    def __init__(self, message: str, code: int = 5) -> None:
        super().__init__(message)
        self.code = code


class Unsupported(ToolError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code=3)


class MissingCredentials(ToolError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code=4)


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

def find_repo_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / ".ai-skills" / "config.yml").is_file():
            return candidate
    raise ToolError(
        "no .ai-skills/config.yml found in this directory or any parent. "
        "Create it with `<suite>/init.sh --write-config`.",
        code=2,
    )


def load_config(root: Path) -> dict[str, Any]:
    text = (root / ".ai-skills" / "config.yml").read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
        return yaml.safe_load(text) or {}
    except ImportError:
        return _parse_yaml_subset(text)


def _coerce(raw: str) -> Any:
    value = raw.strip()
    if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) > 1:
        return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        return [_coerce(p) for p in inner.split(",")] if inner else []
    lowered = value.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    if lowered in ("null", "~", ""):
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def _significant_lines(text: str) -> list[tuple[int, str]]:
    """Line number and content, with blanks, full-line comments, and trailing
    comments removed. Quoted values keep any '#' inside them."""
    out: list[tuple[int, str]] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        line = raw
        if " #" in line:
            head, _, _ = line.partition(" #")
            if head.count('"') % 2 == 0 and head.count("'") % 2 == 0:
                line = head
        line = line.rstrip()
        if line.strip():
            out.append((lineno, line))
    return out


def _parse_yaml_subset(text: str) -> dict[str, Any]:
    """Parse the configuration subset: nested maps, scalars, flow sequences,
    block sequences of scalars, and block sequences of maps.

    Deliberately small. It does not implement YAML; it reads this suite's own
    template shape and raises on anything it does not recognize rather than
    guessing, so a misparse surfaces as an error instead of a wrong value.
    """
    lines = _significant_lines(text)
    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, root)]

    for index, (lineno, line) in enumerate(lines):
        indent = len(line) - len(line.lstrip())
        content = line.strip()

        # A block sequence's items sit at the same indent as their key in this
        # template, so pop only on a strictly smaller indent for list items.
        if content.startswith("- "):
            while len(stack) > 1 and indent < stack[-1][0]:
                stack.pop()
        else:
            while len(stack) > 1 and indent <= stack[-1][0]:
                stack.pop()
        container = stack[-1][1]

        if content.startswith("- "):
            item = content[2:].strip()
            if not isinstance(container, list):
                raise ToolError(
                    f"config.yml line {lineno}: list item under a non-list key", code=2
                )
            if ":" in item and not item.startswith(("'", '"', "[")):
                key, _, rest = item.partition(":")
                entry: dict[str, Any] = {key.strip(): _coerce(rest)}
                container.append(entry)
                # Continuation keys of this entry are indented past the dash.
                stack.append((indent + 1, entry))
            else:
                container.append(_coerce(item))
            continue

        if ":" not in content:
            raise ToolError(f"config.yml line {lineno}: cannot parse {content!r}", code=2)

        key, _, rest = content.partition(":")
        key, rest = key.strip(), rest.strip()
        if not isinstance(container, dict):
            raise ToolError(f"config.yml line {lineno}: mapping inside a list item", code=2)

        if rest != "":
            container[key] = _coerce(rest)
            continue

        # No inline value: the block that follows decides map versus sequence.
        child: Any = {}
        for _, following in lines[index + 1:]:
            following_indent = len(following) - len(following.lstrip())
            if following_indent < indent:
                break
            if following.strip().startswith("- ") and following_indent >= indent:
                child = []
            break
        container[key] = child
        stack.append((indent, child))

    return root


def env_credentials(names: list[str]) -> list[str]:
    values = []
    for name in names or []:
        value = os.environ.get(name)
        if not value:
            raise MissingCredentials(
                f"environment variable {name} is not set. "
                "The suite reads credentials only from the environment."
            )
        values.append(value)
    return values


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

def http(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: Any = None,
) -> Any:
    data = None
    hdrs = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    hdrs.setdefault("Accept", "application/json")
    request = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        if exc.code in (401, 403):
            raise MissingCredentials(
                f"{method} {_redact(url)} returned {exc.code}. "
                "Check the credential variables named in .ai-skills/config.yml."
            ) from exc
        raise ToolError(f"{method} {_redact(url)} returned {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ToolError(f"{method} {_redact(url)} failed: {exc.reason}") from exc
    if not payload.strip():
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return payload


def _redact(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def basic_auth(user: str, token: str) -> str:
    raw = f"{user}:{token}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


# --- Markdown -> Atlassian Document Format ---------------------------------
# Jira Cloud REST v3 accepts ADF, not markdown or wiki markup. Every rich-text
# field a caller writes - a description, a comment - has to be converted, so the
# converter lives here rather than in one operation. Unknown syntax degrades to
# plain text: a document that renders imperfectly is recoverable, one the API
# rejects is not.

INLINE = re.compile(
    r"(?P<code>`[^`]+`)"
    r"|(?P<bold>\*\*[^*]+\*\*)"
    r"|(?P<italic>(?<!\*)\*[^*]+\*(?!\*))"
    r"|(?P<link>\[[^\]]+\]\([^)]+\))"
    r"|(?P<url>https?://[^\s<>()]+)"
)


def inline_nodes(text: str) -> list[dict[str, Any]]:
    """Split one line into ADF text nodes, honouring a small inline subset."""
    nodes: list[dict[str, Any]] = []
    pos = 0
    for m in INLINE.finditer(text):
        if m.start() > pos:
            nodes.append({"type": "text", "text": text[pos:m.start()]})
        kind, raw = m.lastgroup, m.group()
        if kind == "code":
            nodes.append({"type": "text", "text": raw[1:-1], "marks": [{"type": "code"}]})
        elif kind == "bold":
            nodes.append({"type": "text", "text": raw[2:-2], "marks": [{"type": "strong"}]})
        elif kind == "italic":
            nodes.append({"type": "text", "text": raw[1:-1], "marks": [{"type": "em"}]})
        elif kind == "link":
            label, _, href = raw[1:].partition("](")
            nodes.append({"type": "text", "text": label,
                          "marks": [{"type": "link", "attrs": {"href": href[:-1]}}]})
        else:
            nodes.append({"type": "text", "text": raw,
                          "marks": [{"type": "link", "attrs": {"href": raw}}]})
        pos = m.end()
    if pos < len(text):
        nodes.append({"type": "text", "text": text[pos:]})
    return [n for n in nodes if n.get("text")]


def para(text: str) -> dict[str, Any]:
    nodes = inline_nodes(text)
    return {"type": "paragraph", "content": nodes} if nodes else {"type": "paragraph"}


def markdown_to_adf(md: str) -> dict[str, Any]:
    """Markdown subset -> ADF document. Unknown syntax degrades to text."""
    lines = md.replace("\r\n", "\n").split("\n")
    content: list[dict[str, Any]] = []
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            content.append(para(" ".join(buffer).strip()))
            buffer.clear()

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            flush()
            lang = stripped[3:].strip()
            i += 1
            code: list[str] = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            node: dict[str, Any] = {"type": "codeBlock",
                                    "content": [{"type": "text", "text": "\n".join(code) or " "}]}
            if lang:
                node["attrs"] = {"language": lang}
            content.append(node)
            i += 1
            continue

        if not stripped:
            flush()
            i += 1
            continue

        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", stripped):
            flush()
            content.append({"type": "rule"})
            i += 1
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading:
            flush()
            content.append({"type": "heading", "attrs": {"level": len(heading.group(1))},
                            "content": inline_nodes(heading.group(2))})
            i += 1
            continue

        if stripped.startswith(">"):
            flush()
            quote: list[str] = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip().lstrip(">").strip())
                i += 1
            content.append({"type": "blockquote", "content": [para(" ".join(quote))]})
            continue

        bullet = re.match(r"^\s*[-*+]\s+(.*)$", line)
        number = re.match(r"^\s*\d+[.)]\s+(.*)$", line)
        if bullet or number:
            flush()
            ordered = bool(number)
            items: list[dict[str, Any]] = []
            while i < len(lines):
                m = (re.match(r"^\s*\d+[.)]\s+(.*)$", lines[i]) if ordered
                     else re.match(r"^\s*[-*+]\s+(.*)$", lines[i]))
                if not m:
                    break
                items.append({"type": "listItem", "content": [para(m.group(1))]})
                i += 1
            content.append({"type": "orderedList" if ordered else "bulletList",
                            "content": items})
            continue

        buffer.append(stripped)
        i += 1

    flush()
    return {"type": "doc", "version": 1, "content": content or [{"type": "paragraph"}]}


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", value)
    text = re.sub(r"</p\s*>", "\n\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = (
        text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        .replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " ")
    )
    return re.sub(r"\n{3,}", "\n\n", text).strip()


# --------------------------------------------------------------------------
# Adapters
# --------------------------------------------------------------------------

class Adapter:
    name = "abstract"

    def __init__(self, root: Path, config: dict[str, Any]) -> None:
        self.root = root
        self.config = config
        self.settings = (config.get("tracker") or {}).get(self.name) or {}

    def probe(self) -> dict[str, Any]:
        raise Unsupported(f"probe is not implemented for {self.name}")

    def get(self, item_id: str) -> dict[str, Any]:
        raise Unsupported(f"get is not supported by the {self.name} adapter")

    def graph(self, item_id: str) -> dict[str, Any]:
        raise Unsupported(f"graph is not supported by the {self.name} adapter")

    def comments(self, item_id: str) -> list[dict[str, Any]]:
        raise Unsupported(f"comments are not supported by the {self.name} adapter")

    def attachments(self, item_id: str, dest: Path) -> list[dict[str, Any]]:
        raise Unsupported(f"attachments are not supported by the {self.name} adapter")

    def comment(self, item_id: str, body: str) -> dict[str, Any]:
        raise Unsupported(f"commenting is not supported by the {self.name} adapter")

    def transitions(self, item_id: str) -> list[dict[str, Any]]:
        raise Unsupported(f"transitions are not supported by the {self.name} adapter")

    def transition(self, item_id: str, target: str) -> dict[str, Any]:
        raise Unsupported(f"transitions are not supported by the {self.name} adapter")

    def create(self, item_type: str, summary: str, body: str,
               parent: str | None = None, component: str | None = None,
               labels: list[str] | None = None,
               dry_run: bool = False) -> dict[str, Any]:
        raise Unsupported(f"creating an item is not supported by the {self.name} adapter")


class NoneAdapter(Adapter):
    name = "none"

    def probe(self) -> dict[str, Any]:
        return {"adapter": "none", "reachable": True,
                "note": "no tracker configured; requirements come from requirement-context"}

    def get(self, item_id: str) -> dict[str, Any]:
        return {"adapter": "none", "primary": None}

    def graph(self, item_id: str) -> dict[str, Any]:
        return {"parent": None, "children": [], "links": []}

    def comments(self, item_id: str) -> list[dict[str, Any]]:
        return []

    def attachments(self, item_id: str, dest: Path) -> list[dict[str, Any]]:
        return []


class JiraAdapter(Adapter):
    name = "jira"

    def _auth(self) -> dict[str, str]:
        names = self.settings.get("credentials_env") or []
        if len(names) != 2:
            raise MissingCredentials(
                "tracker.jira.credentials_env must name exactly two variables: "
                "the account email and the API token."
            )
        email, token = env_credentials(names)
        return {"Authorization": basic_auth(email, token)}

    def _api(self, path: str) -> str:
        base = str(self.settings.get("base_url", "")).rstrip("/")
        if not base:
            raise ToolError("tracker.jira.base_url is not configured", code=2)
        return f"{base}/rest/api/3{path}"

    def probe(self) -> dict[str, Any]:
        me = http(self._api("/myself"), headers=self._auth())
        return {"adapter": "jira", "reachable": True,
                "account": me.get("displayName"), "account_id": me.get("accountId")}

    def get(self, item_id: str) -> dict[str, Any]:
        fields = ("summary,description,status,issuetype,assignee,reporter,"
                  "parent,subtasks,issuelinks,labels,priority,fixVersions,created,updated")
        issue = http(self._api(f"/issue/{item_id}?fields={fields}"), headers=self._auth())
        f = issue.get("fields", {})
        return {
            "id": issue.get("key"),
            "title": f.get("summary"),
            "type": (f.get("issuetype") or {}).get("name"),
            "status": (f.get("status") or {}).get("name"),
            "status_category": ((f.get("status") or {}).get("statusCategory") or {}).get("key"),
            "assignee": (f.get("assignee") or {}).get("displayName"),
            "description": f.get("description"),
            "labels": f.get("labels") or [],
            "url": f"{str(self.settings.get('base_url','')).rstrip('/')}/browse/{issue.get('key')}",
        }

    def graph(self, item_id: str) -> dict[str, Any]:
        fields = "parent,subtasks,issuelinks,summary,issuetype"
        issue = http(self._api(f"/issue/{item_id}?fields={fields}"), headers=self._auth())
        f = issue.get("fields", {})
        parent = f.get("parent")
        links = []
        for link in f.get("issuelinks") or []:
            other = link.get("outwardIssue") or link.get("inwardIssue") or {}
            links.append({
                "id": other.get("key"),
                "title": (other.get("fields") or {}).get("summary"),
                "type": (other.get("fields") or {}).get("issuetype", {}).get("name"),
                "relation": (link.get("type") or {}).get("name"),
            })
        return {
            "parent": {"id": parent.get("key"),
                       "title": (parent.get("fields") or {}).get("summary")} if parent else None,
            "children": [{"id": s.get("key"),
                          "title": (s.get("fields") or {}).get("summary"),
                          "type": (s.get("fields") or {}).get("issuetype", {}).get("name")}
                         for s in f.get("subtasks") or []],
            "links": links,
        }

    def comments(self, item_id: str) -> list[dict[str, Any]]:
        data = http(self._api(f"/issue/{item_id}/comment?expand=renderedBody&maxResults=100"),
                    headers=self._auth())
        return [{"author": (c.get("author") or {}).get("displayName"),
                 "created": c.get("created"),
                 "body": strip_html(c.get("renderedBody"))}
                for c in data.get("comments", [])]

    def attachments(self, item_id: str, dest: Path) -> list[dict[str, Any]]:
        issue = http(self._api(f"/issue/{item_id}?fields=attachment"), headers=self._auth())
        dest.mkdir(parents=True, exist_ok=True)
        saved = []
        for att in (issue.get("fields", {}).get("attachment") or []):
            target = dest / str(att.get("filename", "attachment"))
            request = urllib.request.Request(att["content"], headers=self._auth())
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                target.write_bytes(response.read())
            saved.append({"name": att.get("filename"), "path": str(target),
                          "size": att.get("size")})
        return saved

    def comment(self, item_id: str, body: str) -> dict[str, Any]:
        payload = {"body": markdown_to_adf(body)}
        created = http(self._api(f"/issue/{item_id}/comment"),
                       method="POST", headers=self._auth(), body=payload)
        return {"id": created.get("id"), "created": created.get("created")}

    def issue_types(self) -> list[str]:
        key = self.settings.get("project_key")
        if not key:
            raise ToolError("tracker.jira.project_key is not configured", code=2)
        data = http(self._api(f"/project/{key}"), headers=self._auth())
        return [t.get("name", "") for t in data.get("issueTypes", []) if not t.get("subtask")]

    def components(self) -> list[str]:
        key = self.settings.get("project_key")
        data = http(self._api(f"/project/{key}/components"), headers=self._auth())
        return [c.get("name", "") for c in data]

    def create(self, item_type: str, summary: str, body: str,
               parent: str | None = None, component: str | None = None,
               labels: list[str] | None = None,
               dry_run: bool = False) -> dict[str, Any]:
        key = self.settings.get("project_key")
        if not key:
            raise ToolError("tracker.jira.project_key is not configured", code=2)
        if not summary.strip():
            raise ToolError("an item needs a summary", code=2)
        if not body.strip():
            raise ToolError("an item needs a description; an empty one is not a defect report",
                            code=2)

        available = self.issue_types()
        if item_type not in available:
            raise ToolError(
                f"issue type {item_type!r} does not exist in {key}. "
                f"Available: {', '.join(available)}"
            )

        # Summary is capped by Jira at 255; 250 leaves room rather than risking a
        # rejection on a boundary the API does not document precisely.
        fields: dict[str, Any] = {
            "project": {"key": key},
            "summary": summary.strip()[:250],
            "issuetype": {"name": item_type},
            "description": markdown_to_adf(body),
        }
        if labels:
            fields["labels"] = [re.sub(r"[^A-Za-z0-9_.-]+", "-", l.strip()).strip("-")
                                for l in labels if l.strip()]
        if parent:
            fields["parent"] = {"key": parent}
        if component:
            existing = self.components()
            if component not in existing:
                raise ToolError(
                    f"component {component!r} does not exist in {key}. "
                    f"Available: {', '.join(existing)}"
                )
            fields["components"] = [{"name": component}]

        # No assignee, priority, sprint, or fix version: triage belongs to the team,
        # and a filed defect that arrives pre-triaged misrepresents who decided.
        if dry_run:
            return {"dry_run": True, "fields": fields}

        created = http(self._api("/issue"), method="POST", headers=self._auth(),
                       body={"fields": fields})
        item_key = created.get("key")
        base = str(self.settings.get("base_url", "")).rstrip("/")
        return {"key": item_key, "url": f"{base}/browse/{item_key}" if base else None,
                "type": item_type, "component": component}

    def transitions(self, item_id: str) -> list[dict[str, Any]]:
        data = http(self._api(f"/issue/{item_id}/transitions"), headers=self._auth())
        return [{"id": t.get("id"), "name": t.get("name"),
                 "to": (t.get("to") or {}).get("name")} for t in data.get("transitions", [])]

    def transition(self, item_id: str, target: str) -> dict[str, Any]:
        available = self.transitions(item_id)
        matches = [t for t in available if t["name"] == target]
        if len(matches) != 1:
            raise ToolError(
                f"expected exactly one transition named {target!r}; found {len(matches)}. "
                f"Available: {[t['name'] for t in available]}"
            )
        before = self.get(item_id)["status"]
        http(self._api(f"/issue/{item_id}/transitions"), method="POST",
             headers=self._auth(), body={"transition": {"id": matches[0]["id"]}})
        after = self.get(item_id)["status"]
        return {"from": before, "to": after, "transition_id": matches[0]["id"],
                "verified": after == matches[0]["to"]}


class OdooAdapter(Adapter):
    name = "odoo"
    _uid: int | None = None

    def _endpoint(self) -> str:
        base = str(self.settings.get("base_url", "")).rstrip("/")
        if not base:
            raise ToolError("tracker.odoo.base_url is not configured", code=2)
        return f"{base}/jsonrpc"

    def _credentials(self) -> tuple[str, str]:
        names = self.settings.get("credentials_env") or []
        if len(names) != 2:
            raise MissingCredentials(
                "tracker.odoo.credentials_env must name exactly two variables: "
                "the login and the API key."
            )
        login, key = env_credentials(names)
        return login, key

    def _rpc(self, service: str, method: str, args: list[Any]) -> Any:
        payload = {"jsonrpc": "2.0", "method": "call",
                   "params": {"service": service, "method": method, "args": args}, "id": 1}
        result = http(self._endpoint(), method="POST", body=payload)
        if isinstance(result, dict) and "error" in result:
            error = result["error"]
            message = (error.get("data") or {}).get("message") or error.get("message")
            raise ToolError(f"odoo rpc error: {message}")
        return result.get("result") if isinstance(result, dict) else result

    def _authenticate(self) -> int:
        if self._uid is not None:
            return self._uid
        login, key = self._credentials()
        database = self.settings.get("database")
        if not database:
            raise ToolError("tracker.odoo.database is not configured", code=2)
        uid = self._rpc("common", "authenticate", [database, login, key, {}])
        if not uid:
            raise MissingCredentials(
                "odoo authentication failed. Check the login and API key named in "
                "tracker.odoo.credentials_env."
            )
        self._uid = int(uid)
        return self._uid

    def _call(self, model: str, method: str, args: list[Any], kwargs: dict | None = None) -> Any:
        login, key = self._credentials()
        return self._rpc("object", "execute_kw",
                         [self.settings["database"], self._authenticate(), key,
                          model, method, args, kwargs or {}])

    def probe(self) -> dict[str, Any]:
        uid = self._authenticate()
        return {"adapter": "odoo", "reachable": True, "uid": uid,
                "database": self.settings.get("database"),
                "project_id": self.settings.get("project_id")}

    def _read_task(self, task_id: str) -> dict[str, Any]:
        fields = ["name", "description", "stage_id", "user_ids", "parent_id",
                  "child_ids", "tag_ids", "project_id", "date_deadline",
                  "priority", "create_date", "write_date"]
        rows = self._call("project.task", "read", [[int(task_id)], fields])
        if not rows:
            raise ToolError(f"odoo task {task_id} not found")
        return rows[0]

    def get(self, item_id: str) -> dict[str, Any]:
        task = self._read_task(item_id)
        stage = task.get("stage_id") or [None, None]
        base = str(self.settings.get("base_url", "")).rstrip("/")
        return {
            "id": str(task["id"]),
            "title": task.get("name"),
            "type": "task",
            "status": stage[1] if isinstance(stage, list) and len(stage) > 1 else None,
            "status_category": None,
            "assignee": None,
            "description": strip_html(task.get("description")),
            "labels": [],
            "url": f"{base}/web#id={task['id']}&model=project.task&view_type=form",
        }

    def graph(self, item_id: str) -> dict[str, Any]:
        task = self._read_task(item_id)
        parent = task.get("parent_id")
        children = []
        if task.get("child_ids"):
            rows = self._call("project.task", "read", [task["child_ids"], ["name"]])
            children = [{"id": str(r["id"]), "title": r.get("name"), "type": "task"}
                        for r in rows]
        return {
            "parent": {"id": str(parent[0]), "title": parent[1]}
            if isinstance(parent, list) and parent else None,
            "children": children,
            "links": [],
            "links_note": "UNSUPPORTED: this Odoo deployment exposes no link relation",
        }

    def comments(self, item_id: str) -> list[dict[str, Any]]:
        domain = [["model", "=", "project.task"], ["res_id", "=", int(item_id)]]
        ids = self._call("mail.message", "search", [domain],
                         {"order": "date asc", "limit": 200})
        if not ids:
            return []
        rows = self._call("mail.message", "read",
                          [ids, ["body", "date", "author_id", "message_type"]])
        return [{"author": (r.get("author_id") or [None, None])[1],
                 "created": r.get("date"),
                 "body": strip_html(r.get("body"))}
                for r in rows if strip_html(r.get("body"))]

    def attachments(self, item_id: str, dest: Path) -> list[dict[str, Any]]:
        domain = [["res_model", "=", "project.task"], ["res_id", "=", int(item_id)]]
        ids = self._call("ir.attachment", "search", [domain], {"limit": 50})
        if not ids:
            return []
        rows = self._call("ir.attachment", "read", [ids, ["name", "datas", "file_size"]])
        dest.mkdir(parents=True, exist_ok=True)
        saved = []
        for row in rows:
            if not row.get("datas"):
                continue
            target = dest / str(row.get("name", "attachment"))
            target.write_bytes(base64.b64decode(row["datas"]))
            saved.append({"name": row.get("name"), "path": str(target),
                          "size": row.get("file_size")})
        return saved

    def comment(self, item_id: str, body: str) -> dict[str, Any]:
        # A log note, not a followers message: an implementation report should
        # be recorded, not emailed to everyone following the task.
        message_id = self._call(
            "project.task", "message_post", [[int(item_id)]],
            {"body": body.replace("\n", "<br/>"),
             "message_type": "comment",
             "subtype_xmlid": "mail.mt_note"},
        )
        return {"id": message_id}

    def transitions(self, item_id: str) -> list[dict[str, Any]]:
        project_id = self.settings.get("project_id")
        domain = [["project_ids", "in", [int(project_id)]]] if project_id else []
        ids = self._call("project.task.type", "search", [domain], {"order": "sequence asc"})
        rows = self._call("project.task.type", "read", [ids, ["name", "sequence"]]) if ids else []
        return [{"id": str(r["id"]), "name": r.get("name"), "to": r.get("name")} for r in rows]

    def transition(self, item_id: str, target: str) -> dict[str, Any]:
        stages = self.transitions(item_id)
        matches = [s for s in stages if s["name"] == target]
        if len(matches) != 1:
            raise ToolError(
                f"expected exactly one stage named {target!r} in this project; "
                f"found {len(matches)}. Available: {[s['name'] for s in stages]}"
            )
        before = self.get(item_id)["status"]
        self._call("project.task", "write", [[int(item_id)], {"stage_id": int(matches[0]["id"])}])
        after = self.get(item_id)["status"]
        return {"from": before, "to": after, "stage_id": matches[0]["id"],
                "verified": after == target}


class GithubAdapter(Adapter):
    name = "github"

    def _repo(self) -> str:
        repo = self.settings.get("repo")
        if not repo or "/" not in str(repo):
            raise ToolError("tracker.github.repo must be configured as owner/name", code=2)
        return str(repo)

    def _gh(self, args: list[str]) -> str:
        try:
            done = subprocess.run(["gh", *args], capture_output=True, text=True,
                                  timeout=TIMEOUT_SECONDS)
        except FileNotFoundError as exc:
            raise ToolError("the `gh` CLI is not installed or not on PATH") from exc
        except subprocess.TimeoutExpired as exc:
            raise ToolError(f"`gh {' '.join(args)}` timed out") from exc
        if done.returncode != 0:
            stderr = done.stderr.strip()
            if "auth" in stderr.lower() or "HTTP 401" in stderr:
                raise MissingCredentials(f"gh is not authenticated: {stderr}")
            raise ToolError(f"`gh {' '.join(args)}` failed: {stderr}")
        return done.stdout

    def probe(self) -> dict[str, Any]:
        self._gh(["auth", "status"])
        return {"adapter": "github", "reachable": True, "repo": self._repo()}

    def get(self, item_id: str) -> dict[str, Any]:
        number = item_id.lstrip("#")
        out = self._gh(["issue", "view", number, "--repo", self._repo(), "--json",
                        "number,title,state,body,labels,assignees,url"])
        data = json.loads(out)
        return {
            "id": f"#{data['number']}",
            "title": data.get("title"),
            "type": "issue",
            "status": data.get("state"),
            "status_category": "done" if data.get("state") == "CLOSED" else "new",
            "assignee": ", ".join(a.get("login", "") for a in data.get("assignees") or []) or None,
            "description": data.get("body"),
            "labels": [l.get("name") for l in data.get("labels") or []],
            "url": data.get("url"),
        }

    def graph(self, item_id: str) -> dict[str, Any]:
        number = item_id.lstrip("#")
        out = self._gh(["issue", "view", number, "--repo", self._repo(),
                        "--json", "body,title"])
        body = json.loads(out).get("body") or ""
        referenced = sorted(set(re.findall(r"#(\d+)", body)))
        return {
            "parent": None,
            "children": [],
            "links": [{"id": f"#{n}", "relation": "referenced-in-body"} for n in referenced],
            "mechanism": "issue body cross-references",
        }

    def comments(self, item_id: str) -> list[dict[str, Any]]:
        number = item_id.lstrip("#")
        out = self._gh(["issue", "view", number, "--repo", self._repo(),
                        "--json", "comments"])
        return [{"author": (c.get("author") or {}).get("login"),
                 "created": c.get("createdAt"),
                 "body": c.get("body")}
                for c in json.loads(out).get("comments", [])]

    def attachments(self, item_id: str, dest: Path) -> list[dict[str, Any]]:
        raise Unsupported(
            "GitHub issues have no attachment API; files appear as links in the body"
        )

    def comment(self, item_id: str, body: str) -> dict[str, Any]:
        number = item_id.lstrip("#")
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                         encoding="utf-8") as handle:
            handle.write(body)
            path = handle.name
        try:
            url = self._gh(["issue", "comment", number, "--repo", self._repo(),
                            "--body-file", path]).strip()
        finally:
            os.unlink(path)
        return {"url": url}

    def transitions(self, item_id: str) -> list[dict[str, Any]]:
        label = self.settings.get("in_review_label")
        if not label:
            raise Unsupported(
                "tracker.github.in_review_label is empty, which disables transitions"
            )
        return [{"id": label, "name": label, "to": label}]

    def transition(self, item_id: str, target: str) -> dict[str, Any]:
        available = self.transitions(item_id)
        if target not in [t["name"] for t in available]:
            raise ToolError(f"{target!r} is not the configured in_review_label")
        number = item_id.lstrip("#")
        self._gh(["issue", "edit", number, "--repo", self._repo(), "--add-label", target])
        after = self.get(item_id)
        return {"from": None, "to": target, "verified": target in after["labels"]}


class FileAdapter(Adapter):
    name = "file"

    def _path(self, item_id: str) -> Path:
        root = self.settings.get("root")
        if not root:
            raise ToolError("tracker.file.root is not configured", code=2)
        return self.root / str(root) / f"{item_id}.md"

    def probe(self) -> dict[str, Any]:
        root = self.root / str(self.settings.get("root", ""))
        return {"adapter": "file", "reachable": root.is_dir(), "root": str(root),
                "items": len(list(root.glob("*.md"))) if root.is_dir() else 0}

    def _read(self, item_id: str) -> str:
        path = self._path(item_id)
        if not path.is_file():
            raise ToolError(f"work item file not found: {path}")
        return path.read_text(encoding="utf-8")

    def _section(self, text: str, heading: str) -> str:
        match = re.search(rf"^##\s+{re.escape(heading)}\s*$(.*?)(?=^##\s|\Z)",
                          text, re.MULTILINE | re.DOTALL | re.IGNORECASE)
        return match.group(1).strip() if match else ""

    def get(self, item_id: str) -> dict[str, Any]:
        text = self._read(item_id)
        title = next((l.lstrip("# ").strip() for l in text.splitlines()
                      if l.startswith("# ")), item_id)
        return {
            "id": item_id,
            "title": title,
            "type": "file",
            "status": None,
            "status_category": None,
            "assignee": None,
            "description": self._section(text, "Requirements")
                           or text.split("## ", 1)[0].strip(),
            "acceptance_criteria": self._section(text, "Acceptance criteria"),
            "labels": [],
            "url": str(self._path(item_id)),
        }

    def graph(self, item_id: str) -> dict[str, Any]:
        text = self._read(item_id)
        links_block = self._section(text, "Links")
        parent = None
        links = []
        for line in links_block.splitlines():
            match = re.match(r"^\s*-\s*(\w+)\s*:\s*(\S+)", line)
            if not match:
                continue
            relation, target = match.group(1).lower(), match.group(2)
            exists = self._path(target).is_file()
            entry = {"id": target, "relation": relation, "exists": exists}
            if relation == "parent":
                parent = entry
            else:
                links.append(entry)
        return {"parent": parent, "children": [], "links": links}

    def comments(self, item_id: str) -> list[dict[str, Any]]:
        log = self._section(self._read(item_id), "Log")
        entries = []
        for block in re.split(r"^###\s+", log, flags=re.MULTILINE):
            if not block.strip():
                continue
            head, _, body = block.partition("\n")
            entries.append({"author": "log", "created": head.strip(),
                            "body": body.strip()})
        return entries

    def attachments(self, item_id: str, dest: Path) -> list[dict[str, Any]]:
        return []

    def comment(self, item_id: str, body: str) -> dict[str, Any]:
        path = self._path(item_id)
        text = path.read_text(encoding="utf-8").rstrip("\n")
        entry = f"\n\n### {date.today().isoformat()}\n\n{body.strip()}\n"
        if re.search(r"^##\s+Log\s*$", text, re.MULTILINE):
            text = text + entry
        else:
            text = text + "\n\n## Log" + entry
        path.write_text(text + "\n", encoding="utf-8")
        return {"path": str(path), "appended": True,
                "note": "working-tree change; the calling workflow stages and commits it"}

    def transitions(self, item_id: str) -> list[dict[str, Any]]:
        raise Unsupported("a Markdown work item has no status model")

    def transition(self, item_id: str, target: str) -> dict[str, Any]:
        raise Unsupported("a Markdown work item has no status model")


ADAPTERS: dict[str, type[Adapter]] = {
    "jira": JiraAdapter,
    "odoo": OdooAdapter,
    "github": GithubAdapter,
    "file": FileAdapter,
    "none": NoneAdapter,
}


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

USAGE = """usage: tracker.sh <operation> [arguments]

  probe
  get <id>
  graph <id>
  comments <id>
  attachments <id> <dest-dir>
  comment <id> <body-file>
  transitions <id>
  transition <id> <target-name>
  create <type> <summary> <body-file> [--parent ID] [--component NAME]
                                      [--label L]... [--dry-run]
"""


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(USAGE)
        return 0 if argv else 2

    operation, args = argv[0], argv[1:]
    try:
        root = find_repo_root(Path.cwd())
        config = load_config(root)
        adapter_name = ((config.get("tracker") or {}).get("adapter") or "none")
        adapter_class = ADAPTERS.get(str(adapter_name))
        if adapter_class is None:
            raise ToolError(
                f"unknown tracker.adapter {adapter_name!r}. "
                f"Expected one of: {', '.join(sorted(ADAPTERS))}",
                code=2,
            )
        adapter = adapter_class(root, config)

        def need(count: int) -> list[str]:
            if len(args) < count:
                raise ToolError(f"`{operation}` needs {count} argument(s)\n\n{USAGE}", code=2)
            return args

        if operation == "probe":
            result: Any = adapter.probe()
        elif operation == "get":
            result = adapter.get(need(1)[0])
        elif operation == "graph":
            result = adapter.graph(need(1)[0])
        elif operation == "comments":
            result = adapter.comments(need(1)[0])
        elif operation == "attachments":
            a = need(2)
            result = adapter.attachments(a[0], Path(a[1]))
        elif operation == "comment":
            a = need(2)
            body = Path(a[1]).read_text(encoding="utf-8")
            if not body.strip():
                raise ToolError("the comment body file is empty", code=2)
            result = adapter.comment(a[0], body)
        elif operation == "transitions":
            result = adapter.transitions(need(1)[0])
        elif operation == "transition":
            a = need(2)
            result = adapter.transition(a[0], a[1])
        elif operation == "create":
            a = need(3)
            body = Path(a[2]).read_text(encoding="utf-8")
            opts, rest = {}, list(a[3:])
            labels: list[str] = []
            while rest:
                flag = rest.pop(0)
                if flag == "--dry-run":
                    opts["dry_run"] = True
                elif flag in ("--parent", "--component", "--label"):
                    if not rest:
                        raise ToolError(f"`{flag}` needs a value", code=2)
                    value = rest.pop(0)
                    if flag == "--label":
                        labels.append(value)
                    else:
                        opts[flag[2:]] = value
                else:
                    raise ToolError(f"unknown option {flag!r}\n\n{USAGE}", code=2)
            result = adapter.create(a[0], a[1], body, labels=labels or None, **opts)
        else:
            raise ToolError(f"unknown operation {operation!r}\n\n{USAGE}", code=2)

        json.dump(result, sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
        return 0

    except ToolError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.code
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
