import { createRouter, createWebHistory } from 'vue-router'
import VehiclesList   from '../views/VehiclesList.vue'
import VehicleDetails from '../views/VehicleDetails.vue'
import DevicesList    from '../views/DevicesList.vue'
import Login          from '../views/Login.vue'
import Docs           from '../views/Docs.vue'
import Tenants        from '../views/Tenants.vue'
import DocsIntro      from '../views/docs/Intro.vue'
import DocsWeb        from '../views/docs/Web.vue'
import DocsTenants    from '../views/docs/Tenants.vue'
import DocsDevices    from '../views/docs/Devices.vue'
import DocsFirmware   from '../views/docs/Firmware.vue'
import DocsApi        from '../views/docs/Api.vue'
import DocsSimulator  from '../views/docs/Simulator.vue'
import DocsSupport    from '../views/docs/Support.vue'
import { useAuth }    from '../composables/useAuth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login',         name: 'login',           component: Login,          meta: { public: true } },
    {
      path: '/docs',
      component: Docs,
      meta: { public: true },
      children: [
        { path: '',           redirect: '/docs/intro' },
        { path: 'intro',      component: DocsIntro },
        { path: 'web',        component: DocsWeb },
        { path: 'tenants',    component: DocsTenants },
        { path: 'devices',    component: DocsDevices },
        { path: 'firmware',   component: DocsFirmware },
        { path: 'api',        component: DocsApi },
        { path: 'simulator',  component: DocsSimulator },
        { path: 'support',    component: DocsSupport }
      ]
    },
    { path: '/',              name: 'vehicles',        component: VehiclesList },
    { path: '/devices',       name: 'devices',         component: DevicesList,    meta: { admin: true } },
    { path: '/vehicles/:id',  name: 'vehicle-details', component: VehicleDetails, props: true },
    { path: '/tenants',       name: 'tenants',         component: Tenants,        meta: { admin: true } }
  ]
})

router.beforeEach((to) => {
  const { isAuthed, isAdmin } = useAuth()
  if (to.meta?.public) return true
  if (!isAuthed.value) return { name: 'login', query: { next: to.fullPath } }
  if (to.meta?.admin && !isAdmin.value) return { name: 'vehicles' }
  return true
})

export default router
