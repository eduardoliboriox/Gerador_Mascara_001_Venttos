from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# === Utilitários ===

def tamanho_efetivo(mascara: str) -> int:
    """
    Conta o tamanho 'efetivo' da máscara, tratando [NUMOP,6] como 6 caracteres.
    """
    return len(mascara.replace("[NUMOP,6]", "X" * 6))

def analisar_mascara_errada(mascara_atual: str, expected_len: int, expected_has_numop: bool):
    """
    Valida a máscara digitada pelo usuário comparando com os requisitos
    derivados da máscara correta do cliente (tamanho efetivo e presença de [NUMOP,6]).
    """
    erros = []
    # Tamanho efetivo (conta [NUMOP,6] como 6)
    if tamanho_efetivo(mascara_atual) != expected_len:
        erros.append(f"❌ Tamanho errado: precisa ter {expected_len} caracteres.")

    # Presença (ou não) de [NUMOP,6]
    has_numop = "[NUMOP,6]" in mascara_atual
    if expected_has_numop and not has_numop:
        erros.append("❌ Faltando '[NUMOP,6]' na máscara.")
    if not expected_has_numop and has_numop:
        erros.append("❌ '[NUMOP,6]' não deveria estar presente para este cliente.")

    # Pelo menos um asterisco (regra geral)
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

def gerar_mascara_exemplo(cliente, modelo):
    if cliente == "HARMAN":
        # Para qualquer modelo Harman, máscara = VEN10100000 + modelo + '*' até 28 caracteres
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
        return "**25*****790372484", ""

    elif cliente == "ELECTROLUX":
        if not modelo.startswith("A") or len(modelo) != 9:
            return None, "❌ Modelo ELECTROLUX inválido. Deve ser no formato A13445103."
        return modelo[1:] + "*" * 11, ""

    elif cliente == "LG":
        if not modelo.startswith("EBR") or len(modelo) != 11:
            return None, "❌ Modelo LG inválido. Deve estar no formato EBRxxxxxxxx."
        numero = modelo[3:]
        return numero + "V57*P****", ""

    elif cliente == "ELGIN":
        if not modelo.startswith("ARC"):
            return None, "❌ Modelo ELGIN inválido. Deve começar com 'ARC'."

        prefixo = modelo[:3]
        digitos = ''.join(c for c in modelo if c.isdigit())
        if len(digitos) < 6:
            return None, "❌ Modelo ELGIN inválido. Não foi possível extrair os 6 dígitos finais."

        ultimos6 = digitos[-6:]
        mascara = f"{prefixo}*******{ultimos6}[NUMOP,6]*****"

        if tamanho_efetivo(mascara) != 27:
            return None, f"❌ Máscara gerada ({mascara}) não tem 27 caracteres efetivos."
        return mascara, ""

    else:
        return None, f"⚠️ Cliente '{cliente}' ainda não está configurado."

# === Rotas Flask ===

@app.route('/')
def index():
    clientes = sorted([
        "HARMAN", "LG", "TCL", "ELGIN", "HQ",
        "ELECTROLUX", "MIDEA"
    ])

    modelos_harman = ["240105", "240092", "240094"]  # pode adicionar outros depois
    modelos_tcl = sorted(["883252", "883257", "883258", "883260", "884949", "884954"])
    modelos_hq = [f"VEHQ10000T{str(i).zfill(6)}" for i in range(1, 81)]
    modelos_midea = sorted(["79037248", "79037267", "79037268", "79037308"])
    modelos_electrolux = [f"A134451{str(i).zfill(2)}" for i in range(2, 16)]
    modelos_lg = [
        "EBR30795409 - RNC5",
        "EBR40618601 - RNC7",
        "EBR31724701 - SNH5",
        "EBR24459501 - SH5A",
        "EBR44845202 - TOUCH NOVA"
    ]
    modelos_elgin = [
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

    modelos = {
        "HARMAN": modelos_harman,
        "TCL": modelos_tcl,
        "HQ": modelos_hq,
        "MIDEA": modelos_midea,
        "ELECTROLUX": modelos_electrolux,
        "LG": modelos_lg,
        "ELGIN": modelos_elgin
    }

    return render_template("index.html", clientes=clientes, modelos=modelos)

@app.route('/gerar', methods=["POST"])
def gerar():
    cliente = request.form["cliente"]
    modelo = request.form["modelo"].strip().split(" - ")[0]  # só o código
    op = request.form["op"].strip().upper()
    tem_mascara = request.form.get("tem_mascara") == "sim"
    mascara_atual = request.form.get("mascara_atual", "").strip()

    if not validar_op(op):
        return jsonify({"erro": "❌ A OP deve conter 5 letras + 6 números."})

    mascara, erro = gerar_mascara_exemplo(cliente, modelo)
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
