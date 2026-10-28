import json
import csv
import os
from datetime import datetime
from substrateinterface import SubstrateInterface

# ==========================================
# CONFIGURACIÓN DE TU GRANJA
# ==========================================
# RPC Oficial de Acurast Mainnet (para Canary usar: wss://public-rpc.canary.acurast.com)
RPC_URL = "wss://public-rpc.mainnet.acurast.com"

# Sustituye por las direcciones reales de tu Manager Wallet y/o de tus 4 Processors
WALLETS = {
    "Manager_Principal": "5CjskL7i1Kj6sfFs3nqmDDWdsKEahJjBZmAW9XEtP4QAkHNC", 
    "Core_Movil_1": "5GXvt2nJSg4612pkM2NQderzRBQrY3FnkCKCn5AEsM4GmnWg",
    "Core_Movil_2": "5ES9EdLVYgDyrAFbgokWCcCBVqNKdLUr8o5u2miUggckSDqm",
    "Lite_Movil_3": "5DvQWjV73eYCgEMqfqHXZdKUewG9Pw6kXvZpWESfGhyp8rfw",
    "Lite_Movil_4": "5F1KmNYWDSzGUtVWEPBYbr9eJQ74oeshFyxjkRZgwXZB81Ku"
}

STATE_FILE = "ultimo_estado_acu.json"
CSV_FILE = "historico_acu.csv"

def obtener_saldos(substrate, direcciones):
    datos = {}
    decimales = substrate.token_decimals or 12  # Acurast usa 12 decimales por defecto
    
    for nombre, direccion in direcciones.items():
        if direccion.startswith("DIRECCION_"):
            continue  # Ignorar placeholders no configurados
        try:
            resultado = substrate.query("System", "Account", [direccion])
            data = resultado.value["data"]
            
            free = data["free"] / (10 ** decimales)
            reserved = data["reserved"] / (10 ** decimales)
            total = free + reserved
            
            datos[nombre] = {
                "direccion": direccion,
                "free": round(free, 6),
                "reserved": round(reserved, 6),
                "total": round(total, 6)
            }
        except Exception as e:
            print(f"[ERROR] No se pudo consultar {nombre} ({direccion}): {e}")
            
    return datos

def main():
    ahora = datetime.now()
    timestamp_str = ahora.strftime("%Y-%m-%d %H:%M:%S")
    
    print(f"Conectando a {RPC_URL}...")
    substrate = SubstrateInterface(url=RPC_URL)
    saldos_actuales = obtener_saldos(substrate, WALLETS)
    
    # Cargar estado anterior si existe
    estado_anterior = {}
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            estado_anterior = json.load(f)
            
    filas_csv = []
    
    print(f"\n--- REPORTE ACURAST ({timestamp_str}) ---")
    
    # Calcular horas transcurridas desde la última medición
    horas_transcurridas = 24.0
    if "timestamp" in estado_anterior:
        dt_anterior = datetime.strptime(estado_anterior["timestamp"], "%Y-%m-%d %H:%M:%S")
        segundos = (ahora - dt_anterior).total_seconds()
        horas_transcurridas = max(segundos / 3600.0, 0.01)
        print(f"Tiempo desde última lectura: {horas_transcurridas:.2f} horas\n")
    else:
        print("Primera ejecución: guardando línea base para futuras comparaciones.\n")

    saldos_previos = estado_anterior.get("saldos", {})
    total_granja_actual = 0.0
    total_delta_granja = 0.0

    for nombre, info in saldos_actuales.items():
        actual_total = info["total"]
        prev_total = saldos_previos.get(nombre, {}).get("total", actual_total)
        
        delta = round(actual_total - prev_total, 6)
        # Normalizar a 24h por si el script se ejecuta en franjas distintas
        media_24h = round((delta / horas_transcurridas) * 24.0, 6) if "timestamp" in estado_anterior else 0.0
        
        total_granja_actual += actual_total
        total_delta_granja += delta
        
        print(f"[{nombre}]")
        print(f"  Saldo Total : {actual_total:.4f} ACU (Libre: {info['free']:.4f} | Reservado: {info['reserved']:.4f})")
        print(f"  Generado    : {delta:+.4f} ACU (Proyección 24h: {media_24h:+.4f} ACU/día)")
        
        filas_csv.append([
            timestamp_str, nombre, info["free"], info["reserved"], 
            actual_total, delta, round(horas_transcurridas, 2), media_24h
        ])

    print("-----------------------------------------")
    print(f"TOTAL GRANJA  : {total_granja_actual:.4f} ACU | Neto generado: {total_delta_granja:+.4f} ACU")

    # Guardar en CSV histórico
    archivo_nuevo = not os.path.exists(CSV_FILE)
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if archivo_nuevo:
            writer.writerow([
                "Fecha_Hora", "Dispositivo_Cuenta", "ACU_Libre", "ACU_Reservado", 
                "ACU_Total", "Delta_ACU", "Horas_Franja", "Ritmo_24h_ACU"
            ])
        writer.writerows(filas_csv)

    # Actualizar estado para el día siguiente
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"timestamp": timestamp_str, "saldos": saldos_actuales}, f, indent=4)

if __name__ == "__main__":
    main()
