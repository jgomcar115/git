

window.addEventListener("DOMContentLoaded", () => {

    const messages = document.createElement("ul");
    document.body.appendChild(messages);
    
    var file = new FileReader();
    file.onload = () => {
        document.getElementById('output').textContent = file.result;
    }


    const websocket = new WebSocket("wss://localhost:8888/",
        {ca: fs.readFileSync("localhost.pem")
        });
    websocket.
    websocket.onmessage = ({ data }) => {
      const message = document.createElement("li");
      const content = document.createTextNode(data);
      message.appendChild(content);
      messages.appendChild(message);
    };
  });