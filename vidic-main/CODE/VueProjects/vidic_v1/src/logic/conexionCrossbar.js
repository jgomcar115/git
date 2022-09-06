import autobahn from "autobahn";

export default {
    conectar(url_server, usuario_crossbar) {
        try {
            let conexion = new autobahn.Connection({
                url: url_server,
                realm: usuario_crossbar
            })
            return conexion
        } catch (error) {
            return null
        }
    }
}