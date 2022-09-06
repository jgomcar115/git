let fecha_fin = Date.now()        				// Instante actual.
let fecha_ini = fecha_fin - (5*60*1000); 		// 5 minutos antes del instante actual.

let div_grafica;								// Contenedor de la gráfica	(sin inicializar).								
let socket;										
let tiempo_real = false

/*
*   Definición de las variables que queremos que se representen.		## AHORA LO OBTENDREMOS CON LA BASE DE DATOS
*/
const VARIABLES = [
	{
		nombre: 'Caudal',
		id: '62c6864e1d847251d90bee10',
		indicador: 'textoCaudal',
		tipo: 'number',
		eje: 'y2',
		unidades: 'm<sup>3</sup>/h', //formato html
		nombre_svg: 'texto_caudal',
        enGrafica: false,
		max_xvalues: MAX_VALORES,
	},
	{
        nombre: 'Oxigeno',
        id: '62c6864f1d847253a1354a2f',
		indicador: 'textoOxigeno',
		tipo: 'number',
		eje: '',
		unidades: 'ppm',
		nombre_svg: 'texto_oxigeno',
        enGrafica: false,
		max_xvalues: MAX_VALORES,
    },
	{
		nombre: 'Soplante',
		id: '62c686501d847252f4897f1b',
		indicador: 'textoSoplante',
		tipo: 'number',
		eje: '',
		unidades: '%',
		nombre_svg: 'undefined',
        enGrafica: false,
		max_xvalues: MAX_VALORES,
	},
	{
        nombre: 'PH',
        id: '62c6864f1d847252411021d7',
		indicador: 'textoPH',
		tipo: 'number',
		eje:'y2',
		unidades: '',
		nombre_svg: 'undefined',
        enGrafica: false,
		max_xvalues: MAX_VALORES,
    }
]

const TOTALIZADORES = [{
		nombre:'Totalizador Hoy',
		id: '62cfe1a81d847278599e196a',
		indicador: 'textoTotalHoy',
		tipo:'number',
		unidades: '',
		nombre_svg: 'undefined',
	},
	{
		nombre:'Totalizador Total',
		id: '62cfe1a91d847278599e196b' ,
		indicador: 'textoTotal' ,
		tipo:'number',
		unidades: '',
		nombre_svg: 'undefined',
	},
	{
		nombre: 'Totalizador Mes',
		id: '62e102341d84725424427141',
		indicador: 'textoTotalMes',
		tipo:'number',
		unidades:'',
		nombre_svg:'undefined',
	}
]

const INDICADORES = [
	{
		nombre: 'nivel_sosa',
		indicador: 'undefined',
		id: '62ce70b21d84722f1c49856f',
		tipo: 'boolean',
		nombre_svg: 'rect_sosa',
	}
	,
	{
		nombre: 'nivel_acido',
		indicador: 'undefined',
		id: '62ce70b11d84722f1c49856e',
		tipo: 'boolean',
		nombre_svg: 'rect_acido',
	}
	//, FALTA POR IMPLEMENTAR
	// {
	// 	nombre_svg: 'nivel_antiespumante',
	// 	id: '',
	// 	tipo: 'boolean'
	// }
]

const numero_trazas = VARIABLES.length;       	//  Guardamos en una variable el número de trazas que van a crearse.
let numero_trazas_escritas = 0;					// Guardamos en una variable el número de trazas que se han dibujado.

// Definimos el diseño de la gráfica.
const disenyo = {
	autosize: false,
	width: $('#contenedorGrafica').width(),
	height: 210,
		font: {
		size: 9,
	},
	margin: {
		l: 26,
		r: 20,
		t: 2, //20
		b: 30
	},
	xaxis: {
		type: 'date',
		//title: 'Fecha-Hora',
		fixedrange: true,
		tickcolor: '#c3c3c3',
		tickfont: {
			//size: 14,
			color: '#c3c3c3'
			},
		linecolor: '#c3c3c3',
	},
	yaxis: {
		//title: 'Valores',
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
	//title: 'VARIABLE',
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

/*
 *	Inicializamos la gráfica una vez se cargue su contenedor en el HTML. 
 */
$('#plotlyDiv').ready(function(){
	div_grafica = document.getElementById("plotlyDiv");
    Plotly.plot(div_grafica, [], disenyo, config);        	 //  se inicializa la gráfica vacía.
	
	// Redimensionar el Gráfico según el espacio disponible.
	const observador = new ResizeObserver (entries => {
		Plotly.relayout('plotlyDiv', {width: $('#contenedorGrafica').width()})
	});
	observador.observe(document.getElementById('contenedorGrafica'));
});

/*
*   Código que se ejecutará una vez se cargue todo el HTML.
*/
$(document).ready(function () {
	let d = new Date(),
        month = '' + (d.getMonth() + 1),
        day = '' + d.getDate(),
        year = d.getFullYear();

    if (month.length < 2) 
        month = '0' + month;
    if (day.length < 2) 
        day = '0' + day;

    let max_day = [year, month, day].join('-');
	document.getElementById('diaIni').setAttribute('max', max_day)
	document.getElementById('diaFin').setAttribute('max', max_day)

	console.log('Comienza el código.')	// MEDIR TIEMPOS
	let inicio = Date.now();			// MEDIR TIEMPOS

    console.log('Comienza la conexión de sockets.')			// MEDIR TIEMPOS
	tiempo_real = true
	conectarSocket();				

	fin = Date.now()										// MEDIR TIEMPOS
	console.log('Termina la conexión de sockets.')			// MEDIR TIEMPOS
	console.log('Tiempo consumido: ' + (fin - inicio))		// MEDIR TIEMPOS
    inicio = fin

	console.log('Comienza obtener datos de Ubidots y escribirlos en la gráfica.')	// MEDIR TIEMPOS

	obtenerDatos(TOKEN, VARIABLES);                                     //  se recogen los datos de las VARIABLES indicadas.
    
	fin = Date.now()										// MEDIR TIEMPOS
	console.log('Termina la recolección de datos.')			// MEDIR TIEMPOS
	console.log('Tiempo consumido: ' + (fin - inicio))		// MEDIR TIEMPOS

	// ubidots.setRealTime(true)                            // ponemos el dashboard en medición del tiempo real.
	
});

function obtenerDatos(token, parametros) {
	numero_trazas_escritas = 0;
    let url = 'https://industrial.api.ubidots.com/api/v1.6/';
    let headers = {
        'X-Auth-Token': token,
        'Content-Type': 'application/json'
    }
    for (let index = 0; index < parametros.length; index++) {
		let k = index
		setTimeout(asynDatos, 0, k)
    }
}

//funcion asíncrona
function asynDatos(index){
	console.log(index)
	let url = 'https://industrial.api.ubidots.com/api/v1.6/';
    let headers = {
        'X-Auth-Token': TOKEN,
        'Content-Type': 'application/json'
    };
	let parametros = VARIABLES
        let url_rango = url + 'variables/' + parametros[index].id + '/statistics/count/' + fecha_ini + '/' + fecha_fin
        let numero_valores = 0

		// let inicio = Date.now()
		// console.log('Primera')
        $.ajax({
            url: url_rango,
            method: 'GET',
            async: false,
            headers: headers,
            success: function (res) {
                numero_valores = res.count
                console.log(numero_valores)		// imprimo por pantalla el número total de valores registrados en el rango indicado.
            }
        })
		// let fin = Date.now()
		// console.log('Fin Primera' + (fin-inicio))

		let nombre = parametros[index].nombre;
		let eje = parametros[index].eje;

		// console.log('Segunda')
		// inicio = Date.now()
		
        if (numero_valores > MAX_VALORES) { //si supera el umbral
			parametros[index].max_xvalues = MAX_VALORES;
            // un tipo de llamada MUESTREANDO los datos
            let url_muestreada = url + 'data/stats/resample/';
            let periodo = Math.ceil(numero_valores / MAX_VALORES); //redondeo techo
            //console.log(periodo)
            let id = parametros[index].id+''

            $.ajax({
                url: url_muestreada,
                dataType: 'json',
                type:'post',
                headers: headers,
                // async:false,
                data: JSON.stringify({"variables":[id], "aggregation":"mean","period":periodo+'T',"join_dataframes":false,"start":fecha_ini,"end":fecha_fin}),
                processData: false,
                success: function (res) {
                    escribirGrafica(res.results[0], nombre, index, 'post', eje)
                },
                error: function (error) { console.log(error) }
            });

        } else if (numero_valores > 0) {
			parametros[index].max_xvalues = numero_valores;
            // llamada normal con page_size igual/menor al numero de valores obtenido
            let url_var = url + 'variables/' + parametros[index].id + '/values?start=' + fecha_ini + '&end=' + fecha_fin + '&page_size=' + numero_valores;
            $.ajax({
                url: url_var,
                method: 'GET',
                headers: headers,
                // async:false,
                success: function (res) {
                    escribirGrafica(res.results, nombre, index, 'get', eje)
                }
            })
        }
		// fin = Date.now()
		// console.log('Fin Segunda: ' + (fin - inicio))
    }

function escribirGrafica(valores, leyenda, index , metodo, eje) {
	let k = index
	console.log('a escribir')
	console.log('numero_trazas:' + numero_trazas_escritas)
	console.log('indice:'+ index)
    if (numero_trazas_escritas == (index)) {
        var trace = {
            x: [],
            y: [],
            type: 'scatter',
            mode: 'lines',
            name: leyenda,
            yaxis: eje,
            // line: {
            // 	width: 3   	// grosor de las líneas
            // }
        };
        if (metodo == 'get') {
            var data = valores.forEach(function (valor) {
                trace.x.push(valor.timestamp);
                trace.y.push(valor.value);
            });
        }
        else if (metodo == 'post') {
            var data = valores.forEach(function (valor) {
                trace.x.push(valor[0]);
                trace.y.push(valor[1]);
            });
        } else {
            alert('Error al cargar los datos. Método erróneo.')
        }
        trace.visible = true
        //if (!visible) trace.visible = 'legendonly'; 			// si se indica no visible -> mostrar solo la leyenda.
        // else Plotly.relayout('plotlyDiv', {title: leyenda});	// si se indica visible -> poner de título del gráfico la variable.
        
		// al obtener los datos se obtiene primero el más nuevo, pero al escribirlos en la gráfica se debe de poner al revés.
        trace.x = trace.x.reverse();
        trace.y = trace.y.reverse();
        Plotly.addTraces(div_grafica, trace);
        numero_trazas_escritas += 1;
        VARIABLES[index].enGrafica = true;
    } else {
		console.log('esperando a la anterior')
        setTimeout(function(){escribirGrafica(valores, leyenda, index, metodo, eje)}, 20)
    }
}

function conectarSocket(){

    // Implementación de la conexión con el server.
    socket = io.connect("https://" + srv,
		{
			path: '/notifications',
			// cors: {
			// 	origin: 'https://prueba115.iot.ubidots.com',
			// 	methods: ["GET", "POST"],
			// 	credentials: true
			withCredentials: true,
			
	});
    var subscribedVars = [];

    // Función para publicar el ID de la variable
    var subscribeVariable = function (variable, callback) {
        // Se publica el ID de la variable que queremos escuchar.
        socket.emit('rt/variables/id/last_value', {
            variable: variable
        });
        // Escuchamos para los cambios.
        socket.on('rt/variables/' + variable + '/last_value', callback);
        subscribedVars.push(variable);
    };

    // Función para desubscribirse de una variable que estemos escuchando.
    var unSubscribeVariable = function (variable) {
        socket.emit('unsub/rt/variables/id/last_value', {
            variable: variable
        });
        var pst = subscribedVars.indexOf(variable);
        if (pst !== -1) {
            subscribedVars.splice(pst, 1);
        }
    };

    //  Implementación de la conexión del socket.
    var connectSocket = function () {
        console.log('Conectando socket...');
        socket.on('connect', function () {
            socket.emit('authentication', { token: TOKEN });
        });
        window.addEventListener('online', function () {
            socket.emit('authentication', { token: TOKEN });
        });
        socket.on('authenticated', function () {
            subscribedVars.forEach(function (variable_id) {
                socket.emit('rt/variables/id/last_value', { variable: variable_id });
            });
        });
    }

	var reconnectSocket = function () {
        console.log('Conectando socket...');
        socket.on('connect', function () {
            socket.emit('authentication', { token: TOKEN });
        });
        window.addEventListener('online', function () {
            socket.emit('authentication', { token: TOKEN });
        });
        socket.on('authenticated', function () {
            subscribedVars.forEach(function (variable_id) {
                socket.emit('rt/variables/id/last_value', { variable: variable_id });
            });
        });
		fecha_fin = Date.now()
		fecha_ini = fecha_fin - (5*60*1000); 
		limpiarGrafica()
		obtenerDatos(TOKEN, VARIABLES)
		tiempo_real = true
		document.getElementById('btnTiempoReal').options[1].selected = true
    }

    connectSocket();
    // Conectamos de nuevo por si se ha perdido la conexión.
    socket.on('reconnect', reconnectSocket);

    socket.on('disconnect', function(){
		tiempo_real = false
        console.log('Desconectando socket.')
    })

    // Nos subscribimos a todas las variables del objeto VARIABLES.
    for (let i = 0; i < VARIABLES.length; i++) {
        subscribeVariable(VARIABLES[i].id, function (value) {               // definimos el callback
            var parsedValue = JSON.parse(value);                            // obtenemos el objeto del objeto JSON.
            //console.log(parsedValue);
            anyadirValorGrafica(parsedValue, i);                            // pasaremos el objeto entero parseado y el índice que ocupa la traza de esa variable.
			actualizarValor(VARIABLES, parsedValue['value'], i)
        })
    }
	for (let i = 0; i < TOTALIZADORES.length; i++) {
		subscribeVariable(TOTALIZADORES[i].id, function (value) {               // definimos el callback
            var parsedValue = JSON.parse(value);                        // obtenemos el objeto del objeto JSON.
			actualizarValor(TOTALIZADORES, parsedValue['value'], i)
        })
	}
	for (let i = 0; i < INDICADORES.length; i++) {
		subscribeVariable(INDICADORES[i].id, function (value) {
			var parsedValue = JSON.parse(value)
			actualizarValor(INDICADORES, parsedValue['value'], i)
		})
	}
}

function anyadirValorGrafica(valorParseado, indice) {
	try{
		if(VARIABLES[indice].enGrafica == true && tiempo_real == true){
			valor = valorParseado['value'].toFixed(2);                                         //  Extraemos el valor del objeto parseado.
			timestamp = valorParseado['timestamp'];                                 //  Extraemos el tiempo para situarlo en la gráfica.
			//console.log('Escribiendo valor:' + valor+ ' tiempo:' + timestamp);
			Plotly.extendTraces(div_grafica, {                                              // Añadimos un nuevo dato a la gráfica (x,y) siendo x=timestamp e y=valor
				x: [[timestamp]],
				y: [[valor]]
			}, [indice],VARIABLES[indice].max_xvalues)
    	}
	} catch {
		console.log('Fallo al escribir un dato desde el socket a tiempo real... Gráfica probablemente vacía en ese momento. No Grave')
	}
    
}

function actualizarValor(arrayVariables, valor, indice){
	let tipo_variable = arrayVariables[indice].tipo;
	let nombre_svg = arrayVariables[indice].nombre_svg;

	if (tipo_variable == 'number'){
		let indicador = arrayVariables[indice].indicador;
    	$('#'+ indicador).html(valor.toFixed(2) + ' ');
		if (nombre_svg != 'undefined') {
		let unidades_de_medida = arrayVariables[indice].unidades;
    		$('#'+ nombre_svg).html(valor.toFixed(2) + unidades_de_medida);
		}
	} else if (tipo_variable == 'boolean'){
		if(valor == 0){
			$('#' + nombre_svg).css('fill', '#f12727');
		} else {
			$('#' + nombre_svg).css('fill', '#3ccd2c');
		}
	} else {
		prompt('El tipo de la variable no ha sido correctamente especificado. [imagen svg]');
	}
}

if(document.getElementById("btnModal")){
	var modal = document.getElementById("myModal");
	var btn = document.getElementById("btnModal");
	var span = document.getElementsByClassName("close")[0];
	var body = document.getElementById("body");
	var accept = document.getElementsByClassName('aceptar')[0];
	var proceso = document.getElementsByClassName('contenedorProceso')[0];

	btn.onclick = function() {
		modal.style.display = "block";
		body.style.position = "static";
		body.style.height = "100%";
		body.style.overflow = "hidden";
		proceso.style.backgroundColor = "#999999";
		proceso.style.borderColor = "#919191";
	}

	span.onclick = function() {
		modal.style.display = "none";
		body.style.position = "inherit";
		body.style.height = "auto";
		body.style.overflow = "visible";
		proceso.style.backgroundColor = "white";
			proceso.style.borderColor = "rgba(242,242,242,255)";
	}

	window.onclick = function(event) {
		if (event.target == modal) {
			modal.style.display = "none";

			body.style.position = "inherit";
			body.style.height = "auto";
			body.style.overflow = "visible";
			proceso.style.backgroundColor = "white";
			proceso.style.borderColor = "rgba(242,242,242,255)";
		}
	}

	accept.onclick = function(event) {
		filtrarFecha();
	}
}

function limpiarGrafica() {
	let trazas = []
	for(let i = 0; i < numero_trazas_escritas; i++){trazas.push(i)}
	for(let i = 0; i < VARIABLES; i++) VARIABLES[i].enGrafica = false
	Plotly.deleteTraces(div_grafica, trazas)
}

function filtrarFecha(){
	try {
		let dia_inicio = document.getElementById('diaIni').valueAsNumber
		let dia_fin = document.getElementById('diaFin').valueAsNumber
		let hora_ini = document.getElementById('horaInicial').valueAsNumber
		let hora_fin = document.getElementById('horaFinal').valueAsNumber

		if (isNaN(dia_inicio) || isNaN(dia_fin) || isNaN(hora_ini) || isNaN(hora_fin)) throw 'NaN'

		if((dia_fin+hora_fin) < (dia_inicio+hora_ini)){
			alert('La fecha final debe ser mayor que la fecha inicial.')
		} else {
			document.getElementsByClassName('close')[0].click();
			fecha_fin = dia_fin + hora_fin - (2 * 60*60*1000)
			fecha_ini = dia_inicio + hora_ini - (2 * 60*60*1000)
			try {	
				tiempo_real = false
				limpiarGrafica();
				obtenerDatos(TOKEN, VARIABLES);  
			} catch (error) {
				console.log(error)
			}
			
		}
	} catch (error) {
		alert('Rellene todos los campos correctamente.')
	}
}

document.getElementById('btnTiempoReal').onchange = function() {
	let valor  = document.getElementById('btnTiempoReal').value;
	if(valor == 'filtro')
		{document.getElementById('btnModal').click(); 
		document.getElementById('btnTiempoReal').options[0].selected = true

	}
	else if(valor == 'No') { /* no hacer nada */}
	else{
		try{
			valor = parseInt(valor)
			fecha_fin = Date.now()
			fecha_ini = fecha_fin - valor * 60 * 1000
			tiempo_real = true
			limpiarGrafica()
			obtenerDatos(TOKEN, VARIABLES)
		} catch (error) {
			console.log ('ERROR: ERROR en el Filtro de Fechas') 
			throw error
		}
	}
}

//.   #####   ###    ###     ###
//.     #     #  #   #  #   #   #
//.     #     ###    ###    #####
//.     #     #      # #    #   #
//.   #####   #      #  #   #   #