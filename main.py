
import json
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


async def broadcast_to_pcs(message):
    for pc in list(pc_connections):
        try:
            await pc.send_text(message)
        except Exception:
            pc_connections.discard(pc)


async def broadcast_to_phones(message):
    for phone in list(phone_connections):
        try:
            await phone.send_text(message)
        except Exception:
            phone_connections.discard(phone)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):

    await websocket.accept()

    role = None
    device_id = None

    try:

        # =====================================================
        # İLK MESAJ
        # =====================================================

        first_message = await websocket.receive_text()

        data = json.loads(first_message)

        role = data.get("role")
        device_id = data.get("device_id")

        # =====================================================
        # PC BAĞLANTISI
        # =====================================================

        if role == "pc":

            pc_connections.add(websocket)

            await send_json(
                websocket,
                {
                    "type": "relay_connected",
                    "message": "AZIZ AI relay bağlantısı başarılı."
                }
            )

            print(
                "[RELAY] AZIZ AI PC bağlandı."
            )

        # =====================================================
        # TELEFON BAĞLANTISI
        # =====================================================

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
                "[RELAY] NEXORA telefon bağlandı:",
                device_id
            )

            # -------------------------------------------------
            # ÖNEMLİ:
            # Telefonun ilk register mesajını PC'ye aktar.
            # -------------------------------------------------

            if data.get("type") == "register":

                print(
                    "[RELAY] Telefon REGISTER gönderdi:",
                    device_id
                )

                await broadcast_to_pcs(
                    first_message
                )

        # =====================================================
        # GEÇERSİZ CİHAZ
        # =====================================================

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

        # =====================================================
        # ANA MESAJ DÖNGÜSÜ
        # =====================================================

        while True:

            message = await websocket.receive_text()

            data = json.loads(message)

            # =================================================
            # TELEFONDAN PC'YE
            # =================================================

            if role == "phone":

                print(
                    "[RELAY] TELEFON -> PC:",
                    data.get("type"),
                    device_id
                )

                await broadcast_to_pcs(
                    message
                )

            # =================================================
            # PC'DEN TELEFONA
            # =================================================

            elif role == "pc":

                target_device = data.get(
                    "target_device_id"
                )

                print(
                    "[RELAY] PC -> TELEFON:",
                    data.get("type"),
                    target_device
                )

                for phone in list(
                    phone_connections
                ):

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
            "[RELAY] Hata:",
            repr(error)
        )

    finally:

        if role == "pc":

            pc_connections.discard(
                websocket
            )

            print(
                "[RELAY] AZIZ AI PC bağlantısı kesildi."
            )

        elif role == "phone":

            phone_connections.discard(
                websocket
            )

            print(
                "[RELAY] NEXORA telefon bağlantısı kesildi:",
                device_id
            )
