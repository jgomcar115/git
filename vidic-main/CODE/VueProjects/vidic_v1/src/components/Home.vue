<template>
    <div>
        <h1>{{msg}}</h1>
        <button @click="acceder" class="btn btn-primary">Acceder a VIDIC</button>
    </div>
</template>
<script>
import {mapState} from 'vuex'

export default {
    name: 'HomeComponent',
    props: {
        msg: String
    },
    computed:{
        ...mapState(['usuario'])
    },
    methods:{
        acceder() {
            console.log(this.usuario)
            if (this.usuario){
                this.$router.push('/menu');
            } else {
                this.$router.push('/login')
            }
        },
    }
}
</script>