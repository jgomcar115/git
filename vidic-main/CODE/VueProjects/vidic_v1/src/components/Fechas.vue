<template>
    <div id="Fechas">
        <div class="contenedorOpcionesGrafica">
                <select id="btnTiempoReal" class="opcionesGrafica" name="tiempoReal">
                        <option disabled value="No"> Filtro </option>
                        <option value="5" selected>&Uacute;ltimos 5 minutos</option>
                        <option value="15">&Uacute;ltimos 15 minutos</option>
                        <option value="30">&Uacute;ltimos 30 minutos</option>
                        <option value="60">&Uacute;ltima hora</option>
                        <option value="120">&Uacute;ltimas 2 horas</option>
                        <option value="filtro">Filtrar Fecha</option>
                    </select>
            <button id="btnModal" class="opcionesGrafica" style="visibility:hidden;">Filtrar Fecha </button>
        </div>

        <div id="myModal" class="modalContainer">
            <div class="modal-content">
                <form onsubmit="">
                    <div class="contenedorFormulario">
                        <div id="contDiaInicial">
                            <p id="labelDiaIni">Fecha Inicio<br> <input type="date" id="diaIni" class="filtroDia" required> </p>
                        </div>
                        <div id="contHoraInicial">
                            <p id="labelHoraInicio">Hora Inicio <br> <input type="time" id="horaInicial" class="filtroHora" required> </p>
                        </div>
                        <div id="contDiaFinal">
                            <p id="labelDiaFin">Fecha Fin<br> <input type="date" id="diaFin" class="filtroDia" required> </p>
                        </div>
                        <div id="contHoraFinal">
                            <p id="labelHoraFin">Hora Fin <br> <input type="time" id="horaFinal" class="filtroHora" required></p>
                        </div>
                    </div>
                    
                    <div style="min-height: 20px;">
                        <div style="float:right;margin-top:5px;">
                            <input type="button" class="close" value="Cancelar">
                            <input type="button" class="aceptar" value="Aceptar">
                        </div>
                    </div>
                    
                </form>
            </div>
        </div>
    </div>
</template>

<script>
    import emitter from '@/logic/emitter'

    export default {
        name: 'FechasCom',
        created() {
            
        },
        mounted () {
            let filtrarFechas = this.filtrarFechas
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
                        filtrarFechas(valor)
                    } catch (error) {
                        console.log ('ERROR: ERROR en el Filtro de Fechas') 
                        throw error
                    }
                }
            }
            if(document.getElementById("btnModal")){
                var modal = document.getElementById("myModal");
                var btn = document.getElementById("btnModal");
                var span = document.getElementsByClassName("close")[0];
                var body = document.getElementById("body");
                var accept = document.getElementsByClassName('aceptar')[0];
                // var proceso = document.getElementsByClassName('contenedorProceso')[0];
                let filtrarFechasPrecisas = this.filtrarFechasPrecisas

                btn.onclick = function() {
                    modal.style.display = "block";
                    body.style.position = "static";
                    body.style.height = "100%";
                    body.style.overflow = "hidden";
                    // proceso.style.backgroundColor = "#999999";
                    // proceso.style.borderColor = "#919191";
                }

                span.onclick = function() {
                    modal.style.display = "none";
                    body.style.position = "inherit";
                    body.style.height = "auto";
                    body.style.overflow = "visible";
                    // proceso.style.backgroundColor = "white";
                    // proceso.style.borderColor = "rgba(242,242,242,255)";
                }

                window.onclick = function(event) {
                    if (event.target == modal) {
                        modal.style.display = "none";

                        body.style.position = "inherit";
                        body.style.height = "auto";
                        body.style.overflow = "visible";
                        // proceso.style.backgroundColor = "white";
                        // proceso.style.borderColor = "rgba(242,242,242,255)";
                    }
                }

                accept.onclick = function() {
                    filtrarFechasPrecisas()
                }
            }
        },
        methods: {
            filtrarFechas (valor) {
                let fechas = {
                    'fecha_fin': Date.now(),
                    'fecha_ini': Date.now() - valor * 60 * 1000
                }
                emitter.emit("indicador-tiempo-real", true);
                emitter.emit("filtrarFecha", fechas);
            },
            filtrarFechasPrecisas () {
                try {
                    let dia_inicio = document.getElementById('diaIni').valueAsNumber;
                    let dia_fin = document.getElementById('diaFin').valueAsNumber
                    let hora_ini = document.getElementById('horaInicial').valueAsNumber
                    let hora_fin = document.getElementById('horaFinal').valueAsNumber
                    if (isNaN(dia_inicio) || isNaN(dia_fin) || isNaN(hora_ini) || isNaN(hora_fin)) throw 'NaN'
                    
                    if((dia_fin+hora_fin) < (dia_inicio+hora_ini)){
                        alert('La fecha final debe ser mayor que la fecha inicial.')
                    } else {
                        document.getElementsByClassName('close')[0].click();
                        let fecha_fin = dia_fin + hora_fin - (2 * 60*60*1000)
                        let fecha_ini = dia_inicio + hora_ini - (2 * 60*60*1000)
                        try {	
                            let fechas = {
                                'fecha_fin': fecha_fin,
                                'fecha_ini': fecha_ini
                            }
                            emitter.emit("filtrarFecha", fechas);
                            emitter.emit("indicador-tiempo-real", false);
                        } catch (error) {
                            console.log(error)
                        }
                    }
                } catch (error) {
                    alert('Rellene todos los campos correctamente.')
                }
            }
        }
    }
</script>