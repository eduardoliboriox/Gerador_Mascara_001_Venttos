from flask import Flask, render_template, request, jsonify
import json, os

app = Flask(__name__)

# === Persistência de modelos em arquivo ===
MODELOS_FILE = "modelos.json"

def carregar_modelos():
    if os.path.exists(MODELOS_FILE):
        with open(MODELOS_FILE, "r") as f:
            return json.load(f)
    else:
        # Modelos iniciais padrão
        return {
            "HARMAN": ["240105", "240092", "240094"],
            "TCL": ["883252", "883257", "883258", "883260", "884949", "884954"],
            "HQ": [f"VEHQ10000T{str(i).zfill(6)}" for i in range(1, 81)],
            "MIDEA": ["79037248", "79037267", "79037268", "79037308"],
            "ELECTROLUX": [f"A134451{str(i).zfill(2)}" for i in range(2, 16)],
            "LG": [
                "EBR30795409 - RNC5",
                "EBR40618601 - RNC7",
                "EBR31724701 - SNH5",
                "EBR24459501 - SH5A",
                "EBR44845202 - TOUCH NOVA"
            ],
            "ELGIN": [
                "ARC141295417500",
                "ARC141295417800",
                "ARC141295418000",
                "ARC141295418100",
                "ARC141295418400",
                "ARC141295418500",
                "ARC141295418800",
                "ARC141295419000",
                "ARC141295419100",
                "ARC141295547400"
            ]
        }

def salvar_modelos(modelos):
    with open(MODELOS_FILE, "w") as f:
        json.dump(modelos, f, indent=2)

# === Utilitários ===
def tamanho_efetivo(mascara: str) -> int:
    return len(mascara.replace("[NUMOP,6]", "X" * 6))

def analisar_mascara_errada(mascara_atual: str, expected_len: int, expected_has_numop: bool):
    erros = []
    if tamanho_efetivo(mascara_atual) != expected_len:
        erros.append(f"❌ Tamanho errado: precisa ter {expected_len} caracteres.")

    has_numop = "[NUMOP,6]" in mascara_atual
    if expected_has_numop and not has_numop:
        erros.append("❌ Faltando '[NUMOP,6]' na máscara.")
    if not expected_has_numop and has_numop:
        erros.append("❌ '[NUMOP,6]' não deveria estar presente para este cliente.")

    if '*' not in mascara_atual:
        erros.append("❌ A máscara precisa conter asteriscos.")

    return erros

def validar_op(op: str) -> bool:
    if len(op) != 11:
        return False
    letras = op[:5]
    numeros = op[5:]
    return letras.isalpha() and numeros.isdigit()

# === Regras de Máscara por Cliente ===
def gerar_mascara_exemplo(cliente, modelo, codigo_completo_elgin=None, codigo_completo_lg=None):
    if cliente == "HARMAN":
        prefixo = "VEN10100000"
        total_length = 28
        mascara = prefixo + modelo
        estrelas = "*" * (total_length - len(mascara))
        return mascara + estrelas, ""

    elif cliente == "HQ":
        if not modelo.startswith("VEHQ10000T") or len(modelo) != 16:
            return None, "❌ Modelo HQ inválido. Deve seguir o padrão VEHQ10000T000001 até VEHQ10000T000080."
        final = modelo[-6:]
        return f"VEHQ1T{final}[NUMOP,6]" + "*" * 5, ""

    elif cliente == "TCL":
        digitos = ''.join([c for c in modelo if c.isdigit()])
        if len(digitos) != 6:
            return None, "❌ Modelo TCL inválido. Deve conter exatamente 6 dígitos."
        return digitos + "[NUMOP,6]" + "*" * 13, ""

    elif cliente == "MIDEA":
        if not modelo.isdigit() or len(modelo) != 8:
            return None, "❌ Modelo MIDEA inválido. Deve conter exatamente 8 dígitos."
        mascara = f"**25*****{modelo}*"
        return mascara, ""

    elif cliente == "ELECTROLUX":
        if not modelo.startswith("A") or len(modelo) != 9:
            return None, "❌ Modelo ELECTROLUX inválido. Deve ser no formato AXXXXXXXX."
        base = modelo[1:]
        mascara = f"{base}****25*****"
        return mascara, ""

    elif cliente == "LG":
        if not codigo_completo_lg or len(codigo_completo_lg) != 19:
            return None, "❌ Para LG, o código completo deve ter 19 caracteres."

        codigo = codigo_completo_lg

        pos_v = codigo.find("V")
        if pos_v < 4:
            return None, "❌ Código LG inválido, não foi possível identificar o 'V'."

        prefixo = codigo[:pos_v+3]  # até V58
        sufixo = codigo[pos_v+3:]

        # Substitui T por * (só primeira ocorrência)
        sufixo = sufixo.replace("T", "*", 1)

        # Troca P + 6 seguintes por P******
        if "P" in sufixo:
            pos_p = sufixo.find("P")
            sufixo = sufixo[:pos_p+1] + "*"*6

        mascara = prefixo + sufixo
        return mascara, ""

    elif cliente == "ELGIN":
        if not codigo_completo_elgin:
            return None, "❌ Para ELGIN, digite o código completo da etiqueta."

        if not codigo_completo_elgin.startswith("ARC"):
            return None, "❌ Código ELGIN inválido, deve começar com 'ARC'."

        sequencia_especial = codigo_completo_elgin[3:10]
        pos_ebr = codigo_completo_elgin.find("EBR")
        if pos_ebr == -1 or pos_ebr < 10:
            return None, "❌ Código ELGIN inválido, não foi possível identificar a posição do EBR."
        modelo_ref = codigo_completo_elgin[pos_ebr-6:pos_ebr]
        mascara = f"ARC{sequencia_especial}{modelo_ref}[NUMOP,6]*****"
        if tamanho_efetivo(mascara) != 27:
            return None, f"❌ Máscara gerada ({mascara}) não tem 27 caracteres efetivos."
        return mascara, ""

    else:
        return None, f"⚠️ Cliente '{cliente}' ainda não está configurado."

# === Rotas Flask ===
@app.route('/')
def index():
    clientes = sorted(["HARMAN", "LG", "TCL", "ELGIN", "HQ", "ELECTROLUX", "MIDEA"])
    modelos = carregar_modelos()
    return render_template("index.html", clientes=clientes, modelos=modelos)

@app.route('/gerar', methods=["POST"])
def gerar():
    cliente = request.form["cliente"]
    op = request.form["op"].strip().upper()
    tem_mascara = request.form.get("tem_mascara") == "sim"
    mascara_atual = request.form.get("mascara_atual", "").strip()
    modelo = request.form.get("modelo", "").strip().split(" - ")[0]
    codigo_completo_elgin = request.form.get("codigo_elgin", "").strip()
    codigo_completo_lg = request.form.get("codigo_lg", "").strip()

    if not validar_op(op):
        return jsonify({"erro": "❌ A OP deve conter 5 letras + 6 números."})

    mascara, erro = gerar_mascara_exemplo(cliente, modelo, codigo_completo_elgin, codigo_completo_lg)
    if not mascara:
        return jsonify({"erro": erro})

    resultado = {
        "mascara": mascara,
        "validacao_op": "✅ OP válida.",
    }

    if tem_mascara:
        expected_len = tamanho_efetivo(mascara)
        expected_has_numop = "[NUMOP,6]" in mascara
        erros = analisar_mascara_errada(mascara_atual, expected_len, expected_has_numop)
        resultado["comparacao"] = erros if erros else ["✅ A máscara anterior já seguia o padrão."]

    return jsonify(resultado)

@app.route('/add_modelo', methods=["POST"])
def add_modelo():
    cliente = request.form["cliente"]
    modelo = request.form["modelo"].strip()

    modelos = carregar_modelos()
    if cliente not in modelos:
        modelos[cliente] = []
    if modelo not in modelos[cliente]:
        modelos[cliente].append(modelo)
        salvar_modelos(modelos)
        return jsonify({"ok": True, "msg": f"Modelo {modelo} adicionado para {cliente}"})
    return jsonify({"ok": False, "msg": "Modelo já existe"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
