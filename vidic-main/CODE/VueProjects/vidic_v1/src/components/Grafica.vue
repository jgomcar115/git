<template>
	<div id="contenedorGrafica" ref="contenedorGrafica" style="max-height:190px">
                    <div id="plotlyDiv" class="contenedorGrafica">
                      
                    </div>
    </div>
</template>

<script>
import dashboard from '@/logic/dashboards';
import Plotly from 'plotly.js-dist'
const $ = require('jquery');
import emitter from '@/logic/emitter';

const id_dispositivo = 1234;

const disenyo = {
	width: $('#contenedorGrafica').width(),
	height: 190,
	font: {
		size: 9,
	},
	autosize: false,
	margin: {
		l: 26,
		r: 20,
		t: 2, //20
		b: 30
	},
	xaxis: {
		type: 'date',
		// title: 'Fecha-Hora',
		fixedrange: true,
		tickcolor: '#c3c3c3',
		tickfont: {
			//size: 14,
			color: '#c3c3c3'
			},
		linecolor: '#c3c3c3',
	},
	yaxis: {
		// title: 'Valores',
		fixedrange: true,
		range: [0,200],
		nticks: 5,
		tickcolor: '#c3c3c3',
		tickfont: {
			//size: 14,
			color: '#c3c3c3'
			},
		linecolor: '#c3c3c3',
	},
	yaxis2: {
		fixedrange: true,
		range: [0,20],
		nticks: 6,
		anchor: 'x',
		overlaying: 'y',
		side: 'right',
		tickfont: {
			//size: 14,
			color: '#c3c3c3'
			},
		linecolor: '#c3c3c3',
	},
	// title: 'VARIABLE',
	legend: {
		"orientation": "h",
		x: 0,
		// y: 1.2,
		y: 1.1,
		bgcolor: "rgba(0,0,0,0)",
		size: 3,
		margin: 5
	}
};
// Definimos la configuración de la gráfica.
const config = {
	responsive: true,
	displayModeBar: false
};

export default {
    name: 'GraficaTiempoReal',
    data: function() {
        return {
			fecha_fin : Date.now(),
			fecha_ini : Date.now() - (5*60*1000),
			graficaEscrita: false,
            datos: {
                'variable_medida_ph': {'indice': -1,'x':[],'y':[], 'nombre': 'PH', 'eje': 'y2', 'enGrafica': false, 'traza':-1, 'max_traza':null},
                'variable_medida_o2': {'indice': -1,'x':[],'y':[], 'nombre': 'Oxigeno', 'eje': '', 'enGrafica': false, 'traza':-1, 'max_traza':null},
                'variable_medida_caudalimetro_entrada': {'indice': -1,'x':[],'y':[], 'nombre': 'Caudal', 'eje': 'y2','enGrafica': false, 'traza':-1, 'max_traza':null},
				'variable_soplante_homogeneizador':{'indice': -1,'x':[],'y':[], 'nombre': 'Soplante', 'eje': '','enGrafica': false, 'traza':-1, 'max_traza':null},
			},
            indices: [],
        }
    },
	created() {
		emitter.on("tiempoRealGraficas", (json) => {
			try{
				console.log('evento recibido')
				for (let idVariable in json){
					let id = 'variable_' + idVariable;
					if(this.datos[id] !== undefined && this.datos[id].enGrafica) {
						Plotly.extendTraces('plotlyDiv', {
							x: [[Date.now()]],
							y: [[json[idVariable]]]
						},[this.datos[id].traza],this.datos[id].max_traza)
					}
				}
			} catch (error) {
				console.log(error)
			}

		});
		emitter.on("filtrarFecha", (fechas) => {
			try{
				this.fecha_ini = fechas['fecha_ini'];
				this.fecha_fin = fechas['fecha_fin'];
				console.log('evento fechas recibido');

				Plotly.deleteTraces('plotlyDiv', this.indices)
				for(let variable in this.datos){
					this.datos[variable].x = []
					this.datos[variable].y = []
				}
				this.indices = []
				this.getDatos()
			} catch (error) {
				console.log(error)
			}
		});		
	},
    methods: {
        async getDatos () {
            try {
                const respuesta = await dashboard.getDispositivo(id_dispositivo, this.fecha_ini, this.fecha_fin)
                console.log(respuesta.data.variables)
				if(this.graficaEscrita == false){
					this.graficaEscrita = true
					Plotly.newPlot('plotlyDiv', [], disenyo, config);
				}

				let traza = 0
                for (let variable in this.datos) {
                    let indice = respuesta.data.variables.findIndex((elemento) => elemento == variable)
                    if(indice >= 0){
						this.datos[variable].indice = indice
                        this.asignarDatos(variable, indice, respuesta.data.datos, traza)
						traza ++;
                    }
                }
                console.log(this.datos)

            } catch (error) {
                console.log(error)
            }
        },
        asignarDatos (variable, indice, datos, traza) {
            for(let dato of datos) {
                this.datos[variable].y.push(dato[indice].toFixed(2))
                this.datos[variable].x.push(dato[dato.length - 1])
            }
			if(this.datos[variable].x.length != 0){
				this.indices.push(traza)
				this.datos[variable].traza = traza;
				traza++;
				this.datos[variable].enGrafica = true;
				var trace = {
					x: this.datos[variable].x,
					y: this.datos[variable].y,
					type: 'scatter',
					mode: 'lines',
					name: this.datos[variable].nombre,
					yaxis: this.datos[variable].eje,
					xaxis: 'xaxis'
				};
				this.datos[variable].max_traza = this.datos[variable].x.length;
				trace.visible = true;
				Plotly.addTraces('plotlyDiv', [trace]);
			}
        },		
    },
    mounted() {
		console.log($('#contenedorGrafica').width(),)
        this.getDatos();
		emitter.on('tiempo-real', function (json) {
			console.log('evento recibido')
			if(this.tiempoRealActivo){
				for (let idVariable in json){
					let id = 'variable_' + idVariable;
					if(this.datos[id] !== undefined && this.datos[id].enGrafica) {
						Plotly.extendTraces('plotlyDiv', {
							x: [[Date.now()]],
							y: [[json[idVariable]]]
						},[this.datos[id].traza])
					}
				}
			}
		});
		console.log(typeof($('#contenedorGrafica')))


		const observador = new ResizeObserver (entries => {
			console.log(entries)		
			Plotly.relayout('plotlyDiv', {width: $('#contenedorGrafica').width()})
		});
		observador.observe(this.$refs.contenedorGrafica);
    }
}
</script>