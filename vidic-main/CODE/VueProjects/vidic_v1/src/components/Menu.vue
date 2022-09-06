<template>
  <div v-if="usuario && dashboards.length>1">
    <header>
      <div class="navbar navbar-dark bg-dark box-shadow">
        <div class="container d-flex justify-content-between">
          <a href="#" class="navbar-brand d-flex align-items-center">
            <strong>Menú Dashboards</strong>
          </a>
          <strong style="color: white" v-if="usuario">Bienvenido {{usuario.nombre}}</strong>
          <strong style="color: white" v-if="!usuario">Nombre de Usuario</strong>
          <button type="button" class="btn btn-dark" @click="logout">Cerrar Sesión</button>
        </div>
      </div>
    </header>

    <main role="main">
      <section class="text-center">
        <div class="container">
          <h1><b>Organización</b></h1>
        </div>
      </section>

      <div class="album py-5 bg-light">
        <div class="container">
          <div class="row">
            <!-- Inicio del bucle -->
            <!-- <div v-for="(item) of dashboards" :key="item.id"> -->
              <div class="col-md-4" v-for="(item, index) of dashboards" :key="item.id">
                <div class="card mb-4 box-shadow">
                  <div class="card-body">
                    <p class="card-text">{{item}}</p>
                    <div class="d-flex justify-content-between align-items-center">
                      <div class="btn-group">
                        <button type="button" class="btn btn-sm btn-outline-secondary" @click="accederDashboard(index)">
                          Entrar
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            <!-- </div> -->
            <!-- Fin del bucle -->
          </div>
        </div>
      </div>
    </main>
  </div>
</template>


<script>
import {mapState} from 'vuex'
import dashboards from '@/logic/dashboards';
// import dashboards from '@/logic/dashboards';

export default {
    name: 'MenuComponent',
    async created() {
      try {
          if(this.usuario == null) this.$router.push('/')
          const respuesta = await dashboards.getDashboards(this.usuario.nombre_usuario);
          console.log(respuesta.data['dashboards'])
          // al voler online es respuesta.data['dashboards'].length
          this.$store.dispatch('actualizarDashboards', respuesta.data['dashboards']);
          // this.$store.dispatch('actualizarDashboards', respuesta['dashboards']);
          if(respuesta.data['dashboards'].length == 1) this.$router.push('/'+ respuesta.data['dashboards'][0])
        } catch (error) {
          console.log(error)
        }
    },
    computed: {
      ...mapState(['usuario']),
      ...mapState(['dashboards'])
    },
    methods:{
      logout () {
        this.$store.dispatch('logout');
        this.$router.push('/')
      },
      accederDashboard (index) {
        this.$router.push('/'+this.dashboards[index])
      }
    }
}

</script>

<style>

:root {
    --jumbotron-padding-y: 3rem;
  }
  
  .jumbotron {
    padding-top: var(--jumbotron-padding-y);
    padding-bottom: var(--jumbotron-padding-y);
    margin-bottom: 0;
    background-color: #fff;
  }
  @media (min-width: 768px) {
    .jumbotron {
      padding-top: calc(var(--jumbotron-padding-y) * 2);
      padding-bottom: calc(var(--jumbotron-padding-y) * 2);
    }
  }
  
  .jumbotron p:last-child {
    margin-bottom: 0;
  }
  
  .jumbotron-heading {
    font-weight: 300;
  }
  
  .jumbotron .container {
    max-width: 40rem;
  }
  
  footer {
    padding-top: 3rem;
    padding-bottom: 3rem;
  }
  
  footer p {
    margin-bottom: .25rem;
  }
  
  .box-shadow { box-shadow: 0 .25rem .75rem rgba(0, 0, 0, .05); }

</style>