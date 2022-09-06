import { createStore } from 'vuex'

export default createStore({
  state: {
    usuario : null,
    dashboards : []
  },
  getters: {
  },
  mutations: {
    actualizarUsuario (state, usuario) {
      state.usuario = usuario;
    },
    actualizarDashboards (state, array) {
      state.dashboards = array;
    },
    logout (state) {
      state.usuario = null;
      state.dashboards = [];
      localStorage.removeItem('access_token');
    }
  },
  actions: {
    async actualizarUsuario (context, usuario) {

      context.commit("actualizarUsuario", usuario);
    },
    async actualizarDashboards (context, array) {
      context.commit("actualizarDashboards", array);
    },
    async logout(context) {
      context.commit("logout");
    }
  },
  modules: {
  }
})
