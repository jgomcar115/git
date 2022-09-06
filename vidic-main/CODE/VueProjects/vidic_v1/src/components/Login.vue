<template>
  <form @submit.prevent="login">
    <section class="vh-100" style="background-color: #00FFFB">
      <div class="container py-5 h-100">
        <div class="row d-flex justify-content-center align-items-center h-100">
          <div class="col-12 col-md-8 col-lg-6 col-xl-5">
            <div class="card shadow-2-strong" style="border-radius: 1rem">
              <div class="card-body p-5 text-center">
                <h3 class="mb-5" style="font-family: 'Russo One', sans-serif">
                  Acceso a la Plataforma
                </h3>
                <div class="form-outline mb-4">
                  <input
                    type="text"
                    id="typeEmailX-2"
                    class="form-control form-control-lg"
                    placeholder="Nombre de usuario"
                    v-model="nombre_usuario"
                  />
                </div>
                <div class="form-outline mb-4">
                  <input
                    type="password"
                    id="typePasswordX-2"
                    class="form-control form-control-lg"
                    placeholder="Contraseña"
                    v-model="contrasenya"
                  />
                </div>
                <button class="btn btn-primary btn-lg btn-block" type="submit">
                  Entrar
                </button>
                <p v-if="fallo_sesion" style="color:red;">Usuario o contraseña no válidos</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  </form>
</template>

<script>
import users from '@/logic/users'
import {mapState} from 'vuex'

export default {
    name: 'LoginComponent',
    data() {
        return {
            nombre_usuario : '',
            contrasenya : '',
            fallo_sesion: false,
        }
    },
    computed: {
        ...mapState(['usuario'])
    },
    methods: {
        async login () {
            try {
                const respuesta = await users.postToken(this.nombre_usuario, this.contrasenya);
                localStorage.setItem('access_token', respuesta.data['access_token']);
                console.log(respuesta);
                this.$store.dispatch('actualizarUsuario', respuesta.data['usuario']);
                // this.$store.dispatch('actualizarUsuario', respuesta); //simulacion offline
                this.$router.push('/menu');

            } catch (error) {
                this.fallo_sesion = true;
                console.log(error)
            }
        },
        actualizarUsuario (usuario) {
          this.$store.dispatch('actualizarUsuario', usuario)
        }
    }
}

</script>