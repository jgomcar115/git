<template>
				<!-- Totalizadores -->
				<div class="contenedorSecundarioTotalizadores">		
					<div class="indicadorTotalizador">
						<span class="labelTotalizadores">
							Total hoy
						</span>
						<span class="valorTotalizadores">
							<span id="textoTotalHoy" class="textoTotalizador">{{dispositivo.variables.totalizador_volumen_dia.valor}}</span> m<sup>3</sup>
						</span>
					</div>
					<div class="indicadorTotalizador">
						<span class="labelTotalizadores">
							Total mes
						</span>
						<span class="valorTotalizadores">
							<span id="textoTotalMes" class="textoTotalizador">{{dispositivo.variables.totalizador_volumen_mes.valor}}</span> m<sup>3</sup>
						</span>
					</div>
					<div class="indicadorTotalizador">
						<span class="labelTotalizadores">
							Total
						</span>
						<span class="valorTotalizadores">
							<span id="textoTotal" class="textoTotalizador">{{dispositivo.variables.totalizador_volumen_total.valor}}</span> m<sup>3</sup>
						</span>
					</div>
				</div>

				<!-- Indicadores -->
				<div class="contenedorSecundarioRegistros">
					<div id="contenedorCaudal" class="indicadorRegistro">
						<p class="parrafoIndicadores">
							CAUDAL <br>m<sup>3</sup>/h<br>
							<span id="textoCaudal" class="textoIndicador">{{dispositivo.variables.medida_caudalimetro_entrada.valor}}</span>
						</p>
					</div>
					<div id="contenedorOxigeno" class="indicadorRegistro">
						<p class="parrafoIndicadores">
							OXIGENO <br>ppm<br>
							<span id="textoOxigeno" class="textoIndicador">{{dispositivo.variables.medida_o2.valor}}</span>
						</p>
					</div>
					<div id="contenedorSoplante" class="indicadorRegistro">
						<p class="parrafoIndicadores">
							SOPLANTE <br>%<br>
							<span id="textoSoplante" class="textoIndicador">{{dispositivo.variables.soplante_homogeneizador.valor}}</span>
						</p>
					</div>
					<div id="contenedorPh" class="indicadorRegistro">
						<p class="parrafoIndicadores">
							PH <br><br>
							<span id="textoPH" class="textoIndicador">{{dispositivo.variables.medida_ph.valor}}</span>
						</p>
					</div>
				</div>
</template>

<script>

import {mapState} from 'vuex'
import emitter from '@/logic/emitter'

// inicialización de variables de la plantilla.
let DISPOSITIVO = {
	'id_dispositivo':'1234',
	'variables':{
		'medida_caudalimetro_entrada':{ //no es el nombre si no el id del dispositivo
			'nombre': 'caudalimetro entrada',
			'valor': 0.0,
		},
		'medida_ph': {
			'nombre': 'medida_ph',
			'valor': 0.0,
		},
		'medida_o2': {
			'nombre': 'medida_02',
			'valor': 0.0,
		},
		'soplante_homogeneizador': {
			'nombre': 'soplante_homogeneizador',
			'valor': 0.0,
		},
		'totalizador_volumen_dia': {
			'nombre': 'totalizador_volumen_dia',
			'valor': 0.0,
		},
		'totalizador_volumen_mes': {
			'nombre': 'totalizador_volumen_mes',
			'valor': 0.0,
		},
		'totalizador_volumen_total': {
			'nombre': 'totalizador_volumen_total',
			'valor': 0.0,
		}
	}
};

export default {
	name: 'Cabecera4Stats',
	data : function() {
			return {
				dispositivo : DISPOSITIVO,
				tiempoRealActivo: true,
			}
		},
	computed: {
		...mapState(['usuario']),
	},
	methods: {
		actualizarVariables(datos){
			for(let id in datos){
				try {
					this.dispositivo.variables[id].valor = datos[id].toFixed(2);
				} catch (error){
					//nada de momento
				}
			}
		},
		actualizarGraficas (json){
			console.log('evento enviado')
			emitter.emit("tiempoReal", json);
		},
		setTiempoReal(valor) {
			this.tiempoRealActivo = valor;
		},
		getTiempoReal() {
			return this.tiempoRealActivo;
		}
	},
	mounted() {
		emitter.on('indicador-tiempo-real',this.setTiempoReal);
		emitter.on('tiempoReal',this.actualizarVariables);
	}
};
</script>