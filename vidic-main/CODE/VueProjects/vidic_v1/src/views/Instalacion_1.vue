<template>
    <div id="app">
        <h1>Instalacion 1 Hello World</h1>
        <button @click="logout">Cerrar Sesión</button>
    </div> 
</template>

<script>


export default {
    components: {

    },
    computed: {

    },
    methods:{
        logout () {
            this.$store.dispatch('logout')
            this.$router.push('/')
        }
    }
}

</script>