<template>
  <div>
    <router-view />
  </div>
</template>

<script>

import users from '@/logic/users'
import {mapState} from 'vuex'

export default {
  name: 'App',
  async created() {
    try{
      let respuesta = await users.getUsuario();
      this.actualizarUsuario(respuesta.data);
      // this.actualizarUsuario(respuesta)   //simulacion offline
    } catch (error) {
      console.log(error);
    }
  },
  computed: {
    ...mapState(['usuario'])
  },
  methods: {
    actualizarUsuario(usuario) {
      this.$store.dispatch('actualizarUsuario', usuario)
      console.log(usuario)
      console.log(this.usuario)
    }
  },
  mounted() {
    
  }
}

</script>

<style>
#app {
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-align: center;
  color: #2c3e50;
}

nav {
  padding: 30px;
}

nav a {
  font-weight: bold;
  color: #2c3e50;
}

nav a.router-link-exact-active {
  color: #42b983;
}
</style>
