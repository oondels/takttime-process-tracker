import express, { Request, Response, NextFunction } from "express";
import http from "http"
import Websocket from "ws"

const app = express();
const port = 3043;
const server = http.createServer(app)
const wss = new Websocket.Server({ server })

app.get("/", (req: Request, res: Response) => {
  res.send("Hello World!");
});

interface WsClient extends Websocket {
  id: string;
  ws: Websocket;
}

interface WsMessage extends Record<any, any> {
  type: string;
  payload: Record<any, any>;
}

const clients: Map<string, WsClient> = new Map()

wss.on("connection", (ws: WsClient) => {
  ws.on("message", (msg: Buffer) => {
    const message: WsMessage = JSON.parse(msg.toString())

    if (message.type === "register") {
      const wsId = message?.payload?.id;
      if (!wsId) {
        console.error("ID do WebSocket não fornecido.");
        return;
      }
      if (wsId.split("-").length < 3) {
        console.error("ID do WebSocket incorreto.");
        return;
      }
      if (clients.has(wsId)) {
        return
      }

      ws.id = wsId;
      clients.set(wsId, ws);
      console.log(`Novo Cliente Registrado: ${ws.id}. Total clientes: ${clients.size}`);
      return;
    }

    else if (message.type === "taktViewer") {
      console.log("Novo vizualizador de takt time conectado.");
      const clientId = message?.clientId;
      if (!clientId) {
        console.error("ID do Cliente não fornecido.");
        return;
      }
      const clientWs = clients.get(clientId);
      if (!clientWs) {
        console.error(`Cliente com ID ${clientId} não encontrado.`);
        return;
      }

      const detectedTime = message?.payload?.takt_time
      if (!detectedTime) {
        console.error("Tempo de takt não fornecido.");
        return;
      }

      console.log(`Enviando alerta de takt time para o cliente ${clientWs.id}: ${detectedTime}`);
      clientWs.send(JSON.stringify({
        type: "taktAlert",
        message: message?.payload?.message,
        takt_time: detectedTime,
        clientId: clientWs.id,
      }));
      return;
    }

    else if (message.type === "repositora_answer") {
      // Fazer logica de resposta. Poder ser confimando ou negando a conclusão do talão de produção da costura
    }

    else if (message.type === "ping") {
      ws.send(JSON.stringify({ type: "pong" }));
      return;
    }
  });

  ws.on("close", () => {
    clients.delete(ws.id);
    console.log(`Cliente desconectado ${ws.id ?? ''}`);
    console.log(`Total clientes: ${clients.size}`);
  });
})

server.listen(port, () => {
  console.log(`Server is running on http://localhost:${port}`);
});