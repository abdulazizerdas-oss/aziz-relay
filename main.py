import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()

pc_connections = set()
phone_connections = {}


@app.get("/")
async def home():
    return {
        "status": "AZIZ RELAY ONLINE",
        "pc": len(pc_connections),
        "phones": len(phone_connections)
    }


async def send_json(ws, data):
    await ws.send_text(
        json.dumps(data, ensure_ascii=False)
    )


async def broadcast_to_pcs(message):
    for pc in list(pc_connections):
        try:
            await pc.send_text(message)
        except Exception:
            pc_connections.discard(pc)


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

        print(
            "[RELAY] İLK MESAJ:",
            role,
            device_id,
            data.get("type")
        )

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
                "[RELAY] PC BAĞLANDI. PC SAYISI:",
                len(pc_connections)
            )

        # =====================================================
        # TELEFON BAĞLANTISI
        # =====================================================

        elif role == "phone":

            if not device_id:
                print("[RELAY] HATA: Telefon device_id göndermedi.")
                await send_json(
                    websocket,
                    {
                        "type": "error",
                        "message": "device_id gerekli."
                    }
                )
                await websocket.close()
                return

            # Aynı device_id varsa eski bağlantıyı kapat
            old_phone = phone_connections.get(device_id)

            if old_phone and old_phone is not websocket:

                try:
                    await old_phone.close()
                except Exception:
                    pass

                print(
                    "[RELAY] Eski telefon bağlantısı kapatıldı:",
                    device_id
                )

            phone_connections[device_id] = websocket

            await send_json(
                websocket,
                {
                    "type": "relay_connected",
                    "message": "NEXORA relay bağlantısı başarılı."
                }
            )

            print(
                "[RELAY] TELEFON BAĞLANDI:",
                device_id
            )

            # Telefon register mesajını PC'ye gönder
            if data.get("type") == "register":

                print(
                    "[RELAY] REGISTER -> PC:",
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

            message_type = data.get("type")

            # =================================================
            # TELEFONDAN PC'YE
            # =================================================

            if role == "phone":

                print(
                    "[RELAY] TELEFON -> PC:",
                    message_type,
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
                    message_type,
                    target_device
                )

                # Belirli telefona gönder
                if target_device:

                    phone = phone_connections.get(
                        target_device
                    )

                    if phone:

                        try:

                            await phone.send_text(
                                json.dumps(
                                    {
                                        **data,
                                        "source": "pc"
                                    },
                                    ensure_ascii=False
                                )
                            )

                            print(
                                "[RELAY] TELEFONA GÖNDERİLDİ:",
                                message_type,
                                target_device
                            )

                        except Exception as error:

                            print(
                                "[RELAY] TELEFONA GÖNDERME HATASI:",
                                repr(error)
                            )

                            phone_connections.pop(
                                target_device,
                                None
                            )

                    else:

                        print(
                            "[RELAY] HEDEF TELEFON BULUNAMADI:",
                            target_device
                        )

                # Hedef belirtilmemişse tüm telefonlara gönder
                else:

                    for phone_id, phone in list(
                        phone_connections.items()
                    ):

                        try:

                            await phone.send_text(
                                message
                            )

                            print(
                                "[RELAY] TÜM TELEFONLARA GÖNDERİLDİ:",
                                phone_id
                            )

                        except Exception:

                            phone_connections.pop(
                                phone_id,
                                None
                            )

    except WebSocketDisconnect:

        print(
            "[RELAY] WebSocket bağlantısı kapandı:",
            role,
            device_id
        )

    except Exception as error:

        print(
            "[RELAY] HATA:",
            repr(error)
        )

    finally:

        if role == "pc":

            pc_connections.discard(
                websocket
            )

            print(
                "[RELAY] PC BAĞLANTISI KESİLDİ."
            )

        elif role == "phone":

            if (
                device_id
                and phone_connections.get(device_id)
                is websocket
            ):

                phone_connections.pop(
                    device_id,
                    None
                )

            print(
                "[RELAY] TELEFON BAĞLANTISI KESİLDİ:",
                device_id
            )
