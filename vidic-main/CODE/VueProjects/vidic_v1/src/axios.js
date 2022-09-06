import axios from 'axios'

axios.defaults.baseURL = 'http://192.168.1.50:8000/';  // ruta del back end API
axios.defaults.headers.common['Authorization'] = 'Bearer '+ localStorage.getItem('access_token');
axios.defaults.headers.common['Access-Control-Allow-Origin'] = '*';
