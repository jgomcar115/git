try {
    var autobahn = require('autobahn');
 } catch (e) {
    // when running in browser, AutobahnJS will
    // be included without a module system
 }
 
 var connection = new autobahn.Connection({
    url: 'ws://192.168.1.52:8080/ws',
    realm: 'realm1'}
 );
 
 connection.onopen = function (session) {
 
    console.log("Connected");

            // SUBSCRIBE to a topic and receive events
            //
            function onhello (args) {
               var msg = args[0];
               console.log("event for 'onhello' received: " + msg);
            }
           
            // session.subscribe('com.example.onhello', onhello).then(
            session.subscribe(' com.myapp.hello', onhello).then(
               function (sub) {
                  console.log("subscribed to topic 'onhello'");
               },
               function (err) {
                  console.log("failed to subscribed: " + err);
               }
            );

    var counter = 0;
            setInterval(function () {

               // PUBLISH an event
               //
               session.publish('com.example.oncounter', [counter]);
               console.log("published to 'oncounter' with counter " + counter);

               // CALL a remote procedure
               //
               session.call('com.example.mul2', [counter, 3]).then(
                  function (res) {
                     console.log("mul2() called with result: " + res);
                  },
                  function (err) {
                     if (err.error !== 'wamp.error.no_such_procedure') {
                        console.log('call of mul2() failed: ' + err);
                     }
                  }
               );

               counter += 1;
            }, 1000);
         };
 
 connection.open();