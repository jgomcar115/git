<template>
    <div id="body" v-if="usuario != null">
        <div id="colorFondo">
            <div class="contenedorPrincipal">
                
                <!-- Logos -->
                <div class="contenedorSecundarioLogos">
                    <div class="contenedorLogoIQD">
                        <img id="logoIQD" src="data:image/png;base64,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" alt="logo IQD">
                    </div>
                    <div class="contenedorLogoReymos">
                        <img id="logoREYMOS" src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAO0AAAA+CAYAAADH55wOAAAAGXRFWHRTb2Z0d2FyZQBBZG9iZSBJbWFnZVJlYWR5ccllPAAAAyppVFh0WE1MOmNvbS5hZG9iZS54bXAAAAAAADw/eHBhY2tldCBiZWdpbj0i77u/IiBpZD0iVzVNME1wQ2VoaUh6cmVTek5UY3prYzlkIj8+IDx4OnhtcG1ldGEgeG1sbnM6eD0iYWRvYmU6bnM6bWV0YS8iIHg6eG1wdGs9IkFkb2JlIFhNUCBDb3JlIDUuNi1jMTMyIDc5LjE1OTI4NCwgMjAxNi8wNC8xOS0xMzoxMzo0MCAgICAgICAgIj4gPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4gPHJkZjpEZXNjcmlwdGlvbiByZGY6YWJvdXQ9IiIgeG1sbnM6eG1wPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvIiB4bWxuczp4bXBNTT0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wL21tLyIgeG1sbnM6c3RSZWY9Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC9zVHlwZS9SZXNvdXJjZVJlZiMiIHhtcDpDcmVhdG9yVG9vbD0iQWRvYmUgUGhvdG9zaG9wIENDIDIwMTUuNSAoTWFjaW50b3NoKSIgeG1wTU06SW5zdGFuY2VJRD0ieG1wLmlpZDoxMUU2QTlGOUE5RDAxMUU2OTFBMDhBMjM3RTMzNUQ2OSIgeG1wTU06RG9jdW1lbnRJRD0ieG1wLmRpZDoxMUU2QTlGQUE5RDAxMUU2OTFBMDhBMjM3RTMzNUQ2OSI+IDx4bXBNTTpEZXJpdmVkRnJvbSBzdFJlZjppbnN0YW5jZUlEPSJ4bXAuaWlkOjExRTZBOUY3QTlEMDExRTY5MUEwOEEyMzdFMzM1RDY5IiBzdFJlZjpkb2N1bWVudElEPSJ4bXAuZGlkOjExRTZBOUY4QTlEMDExRTY5MUEwOEEyMzdFMzM1RDY5Ii8+IDwvcmRmOkRlc2NyaXB0aW9uPiA8L3JkZjpSREY+IDwveDp4bXBtZXRhPiA8P3hwYWNrZXQgZW5kPSJyIj8+glgQLAAAE1BJREFU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" alt="Imagen Logo">
                    </div>
                </div>

                <!-- Componente 1 Estadísticas -->
                <Cabecera4Stats />
            </div>
        </div>
        <!-- Componente 2 y 3 Fechas y Ventana Emergente -->
        <Fechas />
        <!-- Componente 4 Gráfica -->
        <GraficaTiempoReal/>
        <!-- Componente 5 Proceso -->
        <div>
            <!-- <img src="@/assets/dibujo.svg" alt="insertar SVG con la etiqueta image"> -->
            <Proceso></Proceso>
        </div>
        <button @click="logout">Cerrar Sesión</button>
    </div> 
</template>

<script>
import {mapState} from 'vuex'
import Cabecera4Stats from '@/components/Cabecera4Stats.vue'
import GraficaTiempoReal from '@/components/Grafica.vue'
import Fechas from '@/components/Fechas.vue'
import emitter from '@/logic/emitter'
import conexionCrossbar from '@/logic/conexionCrossbar'
import Proceso from '@/components/Proceso.vue'

let url_server = 'ws://192.168.1.41:8080/ws';
let usuario_crossbar = 'realm1';
let id_instalacion = '1111'
let id_dispositivo = '1234'

let conexion;

export default {
    name: 'ReymosView',
    components: {
    Cabecera4Stats,
    GraficaTiempoReal,
    Fechas,
    Proceso
},
    data: function () {
            return {
                tiempoRealActivo: true,
            }
        },
    created() {
        if(this.usuario == null) this.$router.push('/login')
        let permiso = false
        for(let id in this.dashboards) {
            if(this.dashboards[id] == this.$route.path.split('/')[1])permiso = true;break;
        }
        if(!permiso)this.$router.push('/login')
        else {
            try {
                conexion = conexionCrossbar.conectar(url_server, usuario_crossbar);
                let comunicarNuevosValores = this.comunicarNuevosValores;
                let comunicarNuevosValoresGraficas = this.comunicarNuevosValoresGraficas
                let getTiempoReal = this.getTiempoReal;
                conexion.onopen = function(session) {
                    function onmessage(args) {
                        console.log('Mensaje recibido');
                        let datos = args[0];
                        let datosJson = JSON.parse(datos);
                        console.log(datosJson['datos']['datos']);
                        if(getTiempoReal()){
                            comunicarNuevosValoresGraficas(datosJson['datos']['datos']);
                        }
                        comunicarNuevosValores(datosJson['datos']['datos']);
                    }
                    session.subscribe(id_instalacion+'.'+id_dispositivo, onmessage);
                }
                conexion.open();
            } catch (error) {
                console.log(error);
            }
        }
    },
    async unmounted() {
        try {
			conexion.close();
		} catch (error) {
			console.log('Conexiones cerradas')
		}
    },
    computed: {
        ...mapState(['usuario']),
        ...mapState(['dashboards'])
    },
    methods:{
        logout () {
            this.$store.dispatch('logout');
            this.$router.push('/');
        },
        comunicarNuevosValores(datos) {
            emitter.emit('tiempoReal', datos);
        },
        comunicarNuevosValoresGraficas(datos) {
            emitter.emit('tiempoRealGraficas', datos);
        },
        getTiempoReal() {
            return this.tiempoRealActivo;
        },
        setTiempoReal(valor) {
			this.tiempoRealActivo = valor;
		},
    },
    mounted() {
		emitter.on('indicador-tiempo-real',this.setTiempoReal);
    }
    }

</script>