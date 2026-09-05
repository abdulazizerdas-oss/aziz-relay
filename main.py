import os
import json
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()

pc_connections = set()
phone_connections = set()


@app.get("/")
async def home():
    return {
        "status": "AZIZ RELAY ONLINE",
        "pc": len(pc_connections),
        "phones": len(phone_connections)
    }


async def send_json(ws, data):
    await ws.send_text(
        json.dumps(
            data,
            ensure_ascii=False
        )
    )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):

    await websocket.accept()

    role = None

    try:

        first_message = await websocket.receive_text()

        data = json.loads(first_message)

        role = data.get("role")

        if role == "pc":

            pc_connections.add(websocket)

            await send_json(
                websocket,
                {
                    "type": "relay_connected",
                    "message": "AZIZ AI relay bağlantısı başarılı."
                }
            )

            print("AZIZ AI PC bağlandı.")

        elif role == "phone":

            phone_connections.add(websocket)

            await send_json(
                websocket,
                {
                    "type": "relay_connected",
                    "message": "NEXORA relay bağlantısı başarılı."
                }
            )

            print(
                "NEXORA telefon bağlandı:",
                data.get("device_id")
            )

        else:

            await send_json(
                websocket,
                {
                    "type": "error",
                    "message": "Geçersiz cihaz türü."
                }
            )

            await websocket.close()
            return

        while True:

            message = await websocket.receive_text()

            data = json.loads(message)

            # Telefondan PC'ye
            if role == "phone":

                for pc in list(pc_connections):

                    try:
                        await pc.send_text(message)

                    except Exception:
                        pc_connections.discard(pc)

            # PC'den telefonlara
            elif role == "pc":

                target_device = data.get(
                    "target_device_id"
                )

                for phone in list(phone_connections):

                    try:

                        if target_device:

                            await phone.send_text(
                                json.dumps(
                                    {
                                        **data,
                                        "source": "pc"
                                    },
                                    ensure_ascii=False
                                )
                            )

                        else:

                            await phone.send_text(
                                message
                            )

                    except Exception:

                        phone_connections.discard(
                            phone
                        )

    except WebSocketDisconnect:

        pass

    except Exception as error:

        print(
            "Relay hatası:",
            error
        )

    finally:

        if role == "pc":

            pc_connections.discard(
                websocket
            )

            print(
                "AZIZ AI PC bağlantısı kesildi."
            )

        elif role == "phone":

            phone_connections.discard(
                websocket
            )

            print(
                "NEXORA telefon bağlantısı kesildi."
            )
