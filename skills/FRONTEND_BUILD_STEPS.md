# Frontend Build Runbook — Refine + Ant Design (tenant-portal, then admin-portal)

> A step-by-step, copy-paste runbook for building the dashboards yourself with **minimal UI
> work** and light pair-programming with Codex. UI comes from **Ant Design** (ready components)
> and **Refine** (left-menu layout, CRUD wiring, auth). You write functionality, not design.
> Do these in order. Each step says what to build and what to safely hand to Codex.
>
> Build `tenant-portal/` first (full runbook below). `admin-portal/` repeats the same steps with
> a different API base and **no `X-Organization-Id`** (see §12). Keep them as two separate apps.

---

## 0. Mental model (read once)
- **Ant Design** = every component ready-made: `Table` (your datagrid), `Form`, `Modal`, `Upload`,
  `DatePicker`, `Select`, `Steps`, `Tag`, `Descriptions`. You never style primitives.
- **Refine** = the glue: it auto-builds the **left sidebar menu** from your `resources`, and gives
  hooks (`useTable`, `useForm`, `useModalForm`, `useCustomMutation`) + `<List>/<Create>/<Edit>/<Show>`
  wrappers wired to Ant. CRUD screens are ~30 lines each.
- You provide two adapters once: a **`dataProvider`** (talks to your Spring REST) and an
  **`authProvider`** (login/logout/token). Everything else reuses them.
- **What Codex does well here:** repeating a CRUD resource from your template, filling a form's
  field list + validation rules, mapping a DTO. **What to NOT ask Codex:** design/layout — Ant +
  Refine already provide it.

---

## 1. Scaffold a fresh app with `create-refine-app`
Start from an empty folder (the existing skeleton is in git — recoverable):
```bash
cd /Users/inderjeet.singh/Projects/einvoicing
rm -rf tenant-portal
npm create refine-app@latest tenant-portal
```
Choose at the prompts:
- Platform: **Vite**
- UI framework: **Ant Design** (`@refinedev/antd`)
- Data provider: **REST API** (`@refinedev/simple-rest`) — you replace this in §6
- Auth provider: **yes** (generates a stub — you replace it in §5)
- Router: **React Router v6**

This generates a **running app with the left-menu layout (`<ThemedLayoutV2>`), router, providers,
an example CRUD resource, and an `<AuthPage>` login screen already wired** — i.e. Steps 1 and 7 are
done for you. Then add the two extra deps used by the interceptors/custom screens:
```bash
cd tenant-portal
npm i axios @ant-design/icons
```
(Refine bundles TanStack Query — caching/polling for free.)

---

## 2. Env + dev proxy
`vite.config.js` (keep the existing proxy):
```js
server: { port: 5173, proxy: { "/api": "http://localhost:8080" } }
```
`src/config/env.ts`:
```ts
export const env = {
  // "" in dev → relative, uses the Vite proxy. Set VITE_API_BASE_URL in prod.
  apiBase: (import.meta.env.VITE_API_BASE_URL ?? "") + "/api/v1",
};
```

---

## 3. Token store (caching)
`src/lib/tokenStore.ts` — persists tokens + selected org across reloads.
```ts
type Tokens = { accessToken: string; refreshToken: string; expiresIn: number };
const K = { access: "ei.access", refresh: "ei.refresh", user: "ei.user", org: "ei.org" };

export const tokenStore = {
  access: () => localStorage.getItem(K.access),
  refresh: () => localStorage.getItem(K.refresh),
  set: (t: Tokens) => { localStorage.setItem(K.access, t.accessToken); localStorage.setItem(K.refresh, t.refreshToken); },
  user: () => { const v = localStorage.getItem(K.user); return v ? JSON.parse(v) : null; },
  setUser: (u: unknown) => localStorage.setItem(K.user, JSON.stringify(u)),
  org: () => localStorage.getItem(K.org),
  setOrg: (id: string) => localStorage.setItem(K.org, id),
  clear: () => Object.values(K).forEach((k) => localStorage.removeItem(k)),
};
```
> Security note: `localStorage` is the fast, simple choice for an internal dashboard but is
> readable by any injected script (XSS). Acceptable to start; the hardened upgrade later is
> access-token-in-memory + refresh-token in an httpOnly cookie (needs a small backend change).
> Never `console.log` tokens; keep `dangerouslySetInnerHTML` out of the app.

---

## 4. Axios client with interceptors (auth + org header + refresh)
`src/lib/http.ts`:
```ts
import axios from "axios";
import { env } from "../config/env";
import { tokenStore } from "./tokenStore";

export const http = axios.create({ baseURL: env.apiBase });

http.interceptors.request.use((config) => {
  const token = tokenStore.access();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  const org = tokenStore.org();
  // Tenant business calls need the org header; auth calls do not.
  if (org && !config.url?.startsWith("/auth")) config.headers["X-Organization-Id"] = org;
  return config;
});

let refreshing: Promise<string | null> | null = null;
http.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retry && tokenStore.refresh()) {
      original._retry = true;
      refreshing ??= axios
        .post(`${env.apiBase}/auth/refresh`, { refreshToken: tokenStore.refresh() })
        .then((res) => { tokenStore.set(res.data); return res.data.accessToken as string; })
        .catch(() => { tokenStore.clear(); location.assign("/login"); return null; })
        .finally(() => { refreshing = null; });
      const newToken = await refreshing;
      if (newToken) { original.headers.Authorization = `Bearer ${newToken}`; return http(original); }
    }
    return Promise.reject(error);
  }
);
```
> For **admin-portal**, the only differences: `env.apiBase = ".../api/v1/admin"` and **remove the
> `X-Organization-Id` line** (admin is global).

---

## 5. authProvider (Refine)
`src/providers/authProvider.ts`:
```ts
import type { AuthProvider } from "@refinedev/core";
import { http } from "../lib/http";
import { tokenStore } from "../lib/tokenStore";

export const authProvider: AuthProvider = {
  login: async ({ email, password }) => {
    const { data } = await http.post("/auth/login", { email, password });
    tokenStore.set(data);
    const me = await http.get("/auth/me");
    tokenStore.setUser(me.data);
    const firstOrg = me.data.memberships?.[0]?.organizationId;
    if (firstOrg) tokenStore.setOrg(firstOrg);           // TODO: org switcher if >1
    return { success: true, redirectTo: "/" };
  },
  logout: async () => {
    try { await http.post("/auth/logout", { refreshToken: tokenStore.refresh() }); } catch { /* noop */ }
    tokenStore.clear();
    return { success: true, redirectTo: "/login" };
  },
  check: async () => (tokenStore.access() ? { authenticated: true } : { authenticated: false, redirectTo: "/login" }),
  onError: async (error) => (error?.response?.status === 401 ? { logout: true } : {}),
  getIdentity: async () => tokenStore.user(),
  getPermissions: async () => tokenStore.user()?.platformRole ?? null,
};
```

---

## 6. dataProvider (maps Refine → your Spring REST + `Page<T>`)
`src/providers/dataProvider.ts` (custom because Spring paginates as `?page=&size=` + `{content,totalElements}`):
```ts
import type { DataProvider } from "@refinedev/core";
import { http } from "../lib/http";
import { env } from "../config/env";

export const dataProvider: DataProvider = {
  getApiUrl: () => env.apiBase,
  getList: async ({ resource, pagination }) => {
    const page = (pagination?.current ?? 1) - 1;
    const size = pagination?.pageSize ?? 20;
    const { data } = await http.get(`/${resource}`, { params: { page, size } });
    return { data: data.content, total: data.totalElements };
  },
  getOne: async ({ resource, id }) => ({ data: (await http.get(`/${resource}/${id}`)).data }),
  create: async ({ resource, variables }) => ({ data: (await http.post(`/${resource}`, variables)).data }),
  update: async ({ resource, id, variables }) => ({ data: (await http.put(`/${resource}/${id}`, variables)).data }),
  deleteOne: async ({ resource, id }) => ({ data: (await http.delete(`/${resource}/${id}`)).data }),
  // For actions like issue/cancel/submit/archive:
  custom: async ({ url, method, payload }) => ({ data: (await http.request({ url, method, data: payload })).data }),
};
```

---

## 7. Adjust the generated shell (`src/App.tsx`)
`create-refine-app` already generated `App.tsx` with `<Refine>`, `<ThemedLayoutV2>` (left menu),
routes, and `<AuthPage>`. You only need to: **(a)** set the theme primary to the brand green,
**(b)** point `dataProvider`/`authProvider` to your Spring ones (§5–§6), **(c)** replace the
example `resources` with yours, **(d)** add each resource's routes. Target shape:
```tsx
import { Refine } from "@refinedev/core";
import { ThemedLayoutV2, useNotificationProvider, AuthPage, ErrorComponent } from "@refinedev/antd";
import routerBindings, { NavigateToResource, CatchAllNavigate } from "@refinedev/react-router-v6";
import { BrowserRouter, Routes, Route, Outlet } from "react-router-dom";
import { Authenticated } from "@refinedev/core";
import { App as AntApp, ConfigProvider } from "antd";
import { FileTextOutlined, TeamOutlined, ShopOutlined, CloudUploadOutlined } from "@ant-design/icons";
import "@refinedev/antd/dist/reset.css";
import { authProvider } from "./providers/authProvider";
import { dataProvider } from "./providers/dataProvider";
import { CustomerList, CustomerCreate, CustomerEdit } from "./pages/customers";

export default function App() {
  return (
    <BrowserRouter>
      <ConfigProvider theme={{ token: { colorPrimary: "#28705f", borderRadius: 8 } }}>
        <AntApp>
          <Refine
            dataProvider={dataProvider}
            authProvider={authProvider}
            routerProvider={routerBindings}
            notificationProvider={useNotificationProvider}
            resources={[
              { name: "invoices",  list: "/invoices",  create: "/invoices/new", edit: "/invoices/:id/edit", show: "/invoices/:id", meta: { label: "Invoices", icon: <FileTextOutlined /> } },
              { name: "customers", list: "/customers", create: "/customers/new", edit: "/customers/:id/edit", meta: { label: "Customers", icon: <TeamOutlined /> } },
              { name: "products",  list: "/products",  create: "/products/new",  edit: "/products/:id/edit",  meta: { label: "Products", icon: <ShopOutlined /> } },
              { name: "einvoice/batches", list: "/einvoice/batches", meta: { label: "E-Invoice Submissions", icon: <CloudUploadOutlined /> } },
            ]}
            options={{ syncWithLocation: true }}
          >
            <Routes>
              <Route element={
                <Authenticated key="app" fallback={<CatchAllNavigate to="/login" />}>
                  <ThemedLayoutV2><Outlet /></ThemedLayoutV2>
                </Authenticated>
              }>
                <Route index element={<NavigateToResource resource="invoices" />} />
                <Route path="/customers">
                  <Route index element={<CustomerList />} />
                  <Route path="new" element={<CustomerCreate />} />
                  <Route path=":id/edit" element={<CustomerEdit />} />
                </Route>
                {/* add products, invoices, batches routes the same way */}
                <Route path="*" element={<ErrorComponent />} />
              </Route>
              <Route element={
                <Authenticated key="auth" fallback={<Outlet />}><NavigateToResource resource="invoices" /></Authenticated>
              }>
                <Route path="/login" element={<AuthPage type="login" />} />
              </Route>
            </Routes>
          </Refine>
        </AntApp>
      </ConfigProvider>
    </BrowserRouter>
  );
}
```
After this you have: **auth screen** (`<AuthPage>` — ready login form), **left-side menu** (auto
from `resources`), **token caching + refresh** (steps 3–4), and route guards. The generator gave
the shell; steps 3–6 make it talk to your Spring backend.

---

## 8. A CRUD resource = your template (Customers). Reuse it for everything.
`src/pages/customers/index.tsx` — **datagrid (list) + create + edit**, all Ant:
```tsx
import { List, useTable, EditButton, Create, Edit, useForm } from "@refinedev/antd";
import { Table, Space, Form, Input, InputNumber, Select } from "antd";

export const CustomerList = () => {
  const { tableProps } = useTable({ syncWithLocation: true }); // wires paging/sort to your dataProvider
  return (
    <List>
      <Table {...tableProps} rowKey="id">
        <Table.Column dataIndex="name" title="Name" />
        <Table.Column dataIndex="trn" title="TRN" />
        <Table.Column dataIndex="email" title="Email" />
        <Table.Column dataIndex="status" title="Status" />
        <Table.Column title="Actions" render={(_, r: any) => <Space><EditButton hideText recordItemId={r.id} /></Space>} />
      </Table>
    </List>
  );
};

const CustomerForm = () => (
  <>
    <Form.Item label="Name" name="name" rules={[{ required: true }]}><Input /></Form.Item>
    <Form.Item label="TRN" name="trn" rules={[{ pattern: /^\d{15}$/, message: "15 digits" }]}><Input /></Form.Item>
    <Form.Item label="Email" name="email" rules={[{ type: "email" }]}><Input /></Form.Item>
    <Form.Item label="Currency" name="currency" initialValue="AED">
      <Select options={["AED","USD","EUR","GBP"].map(v => ({ value: v, label: v }))} />
    </Form.Item>
    <Form.Item label="Payment terms (days)" name="paymentTermsDays"><InputNumber min={0} /></Form.Item>
  </>
);

export const CustomerCreate = () => { const { formProps, saveButtonProps } = useForm();
  return <Create saveButtonProps={saveButtonProps}><Form {...formProps} layout="vertical"><CustomerForm /></Form></Create>; };

export const CustomerEdit = () => { const { formProps, saveButtonProps } = useForm();
  return <Edit saveButtonProps={saveButtonProps}><Form {...formProps} layout="vertical"><CustomerForm /></Form></Edit>; };
```
**This ~40-line file is your pattern.** Products is the same with different fields — a perfect
Codex task (see §11). Validation is Ant `rules` (mirror the backend constraints).

---

## 9. Modals (create/edit in a dialog instead of a page)
Use `useModalForm` — a ready modal + form, zero design:
```tsx
import { useModalForm, Create } from "@refinedev/antd";
import { Modal, Form, Input } from "antd";

const { modalProps, formProps, show } = useModalForm({ action: "create", resource: "customers" });
// trigger: <Button onClick={() => show()}>New customer</Button>
<Modal {...modalProps} title="New customer">
  <Form {...formProps} layout="vertical"><Form.Item name="name" label="Name" rules={[{ required: true }]}><Input /></Form.Item></Form>
</Modal>
```
For confirm dialogs (issue/cancel/archive), use Ant `Modal.confirm(...)` or Refine `<DeleteButton>`.

## 9.1 Custom actions (issue / cancel / submit / revalidate)
```tsx
import { useCustomMutation, useInvalidate } from "@refinedev/core";
const { mutate } = useCustomMutation();
const invalidate = useInvalidate();
// Issue an invoice:
mutate({ url: `/invoices/${id}/issue`, method: "post", values: {} }, {
  onSuccess: () => invalidate({ resource: "invoices", invalidates: ["list", "detail"] }),
  onError: (e) => {/* e.response.data.message has the FTA rule codes → show in a notification */},
});
```

---

## 10. The two custom screens (build these by hand; Codex helps wire, not design)

### 10.1 Invoice editor (`/invoices/new`, `/invoices/:id/edit`)
Not plain CRUD (line items + live totals + compliance). Use `useForm` + Ant `Form.List`:
```tsx
// header fields (customer Select from useSelect, type, currency, dates...) then line items:
<Form.List name="lines">
  {(fields, { add, remove }) => (<>
    {fields.map((f) => (
      <Space key={f.key} align="baseline">
        <Form.Item {...f} name={[f.name, "description"]} rules={[{ required: true }]}><Input placeholder="Description" /></Form.Item>
        <Form.Item {...f} name={[f.name, "quantity"]} rules={[{ required: true }]}><InputNumber min={0.0001} /></Form.Item>
        <Form.Item {...f} name={[f.name, "unitPrice"]} rules={[{ required: true }]}><InputNumber min={0} /></Form.Item>
        <Form.Item {...f} name={[f.name, "vatCategory"]} initialValue="STANDARD"><Select options={vatOptions} /></Form.Item>
        <MinusCircleOutlined onClick={() => remove(f.name)} />
      </Space>
    ))}
    <Button onClick={() => add()} icon={<PlusOutlined />}>Add line</Button>
  </>)}
</Form.List>
```
- **Live totals:** read `Form.useWatch("lines", form)` and compute a preview (qty*price, *5% for
  STANDARD) in a `<Descriptions>` — backend is authoritative.
- **Compliance:** after Save, the invoice response carries `complianceStatus` + `complianceIssues`;
  render a `<Tag color=...>` + an `<Alert>`/`<List>` of issues. Disable the **Issue** button unless
  `COMPLIANT` (tooltip lists what's missing).

### 10.2 Bulk e-invoice submission (`/einvoice/batches`)
- **Upload:** Ant `<Upload.Dragger accept=".xlsx,.csv">` → POST multipart to
  `/einvoice/batches/upload` (use `http.post` with `FormData`).
- **Batch detail:** poll with Refine and drive an Ant `<Steps>` from `state`:
```tsx
const { data } = useOne({ resource: "einvoice/batches", id, queryOptions: {
  refetchInterval: (q) => (["COMPLETED","FAILED","EXPIRED","CANCELLED"].includes(q?.state?.data?.data?.state) ? false : 4000),
}});
// map data.state → <Steps current={...}> ; render items table + per-item validationErrors ;
// buttons: Revalidate (PLATFORM_ACTION_REQUIRED/ASP_ACTION_REQUIRED), Submit (PLATFORM_VALIDATED)
```

---

## 11. Pair-programming with Codex (do this, it's the speed unlock)
Codex is weak at design — so **never** ask it to lay out screens. Ask it to **replicate your
template** and **wire data**. Effective task prompts:
- *"Using `src/pages/customers/index.tsx` as the exact template, create `src/pages/products/index.tsx`
  with fields: type (Select GOODS/SERVICE, required), name (required), sku, unitOfMeasure, unitPrice
  (InputNumber, required, >0), currency (Select AED/USD/EUR/GBP), vatCategory (Select). Same
  `useTable`/`useForm`/`List`/`Create`/`Edit` structure. Don't change styling."*
- *"Add the `products` routes to `App.tsx` mirroring the `customers` routes."*
- *"Write the Zod-equivalent Ant `rules` for `InvoiceRequest` from `docs/FRONTEND_DASHBOARD_GUIDE.md` §9.4."*
- *"Implement `dataProvider.getList` filters: accept a `status` filter and pass it as a query param."*

Rules for Codex tasks: give it (1) the template file path, (2) the exact field list + validation,
(3) "match the existing structure, no new design." Review its diff — it should look like your
template. Keep each task to one file.

**You build by hand:** the shell (§1–§7 — do once), the two custom screens (§10). **Codex builds:**
every additional CRUD resource from the customers template, form field lists, route additions, data
mapping tweaks.

---

## 12. admin-portal (scaffold fresh the same way, 3 differences)
Scaffold its own app, then repeat §2–§11:
```bash
cd /Users/inderjeet.singh/Projects/einvoicing && rm -rf admin-portal
npm create refine-app@latest admin-portal   # same choices: Vite + Ant Design + REST + auth + RR v6
```
Then apply §2–§11 with these differences:
1. `env.apiBase = (VITE_API_BASE_URL ?? "") + "/api/v1/admin"`.
2. In `http.ts`, **delete the `X-Organization-Id` line** (admin is global).
3. `resources` = organizations, asps, validation-rules, users, audit, monitoring — mostly plain
   CRUD (so mostly Codex from the customers template). No invoice-editor/bulk screens.
Keep it a **separate app** (separate build/deploy), sharing only the pattern.

---

## 13. Run
```bash
# backend up (docker compose up --build) and seeded, then:
cd tenant-portal && npm run dev      # http://localhost:5173
```
Log in with a seeded tenant user (see backend README seed). You'll land on Invoices with the left
menu, ready CRUD, and token caching working across reloads.

---

## 14. Order of attack (checklist)
- [ ] §1 scaffold fresh with `create-refine-app` → **running shell (layout + AuthPage) out of the box**
- [ ] §2 env + Vite proxy
- [ ] §3–§4 tokenStore + axios interceptors (auth, org header, refresh)
- [ ] §5–§6 replace generated stubs with the Spring authProvider + custom dataProvider
- [ ] §7 adjust generated `App.tsx` (theme, providers, your resources + routes)
- [ ] §8 Customers CRUD (your template) → verify list/create/edit end-to-end
- [ ] §11 hand Products (+ any other CRUD) to Codex from the template
- [ ] §10.1 Invoice editor (by hand) + issue/cancel actions (§9.1)
- [ ] §10.2 Bulk upload + batch state-machine detail (by hand)
- [ ] §12 scaffold + build admin-portal (mostly Codex)
