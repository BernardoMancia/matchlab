import os
from openai import OpenAI
from ..config import OPENAI_API_KEY, OPENAI_MODEL

def analyze_with_openai(dossier: dict, mode: str = "full") -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY não definido.")
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
    client = OpenAI()

    instructions = (
        "Você é um analista profissional de futebol.\n"
        "Regra ABSOLUTA: use SOMENTE os dados do DOSSIÊ JSON. "
        "Se algo não existir no dossiê, escreva 'DADO AUSENTE' e faça suposição conservadora.\n\n"
        "Formato obrigatório:\n"
        "1) Jogador por jogador (provável XI vs provável XI) por setores.\n"
        "2) Por equipe (ataque/meio/defesa/bolas paradas/momento).\n"
        "3) Time x time (roteiro + 3 chaves táticas).\n"
        "4) Previsão com UM ÚNICO placar mais provável no final:\n"
        "PLACAR_MAIS_PROVAVEL: TimeCasa X–Y TimeFora\n"
        "Depois: Risco (2 bullets) e Confiança (0-100).\n\n"
        "Se mode=compact: curto, mas mantendo o PLACAR_MAIS_PROVAVEL."
    )

    resp = client.responses.create(
        model=OPENAI_MODEL,
        reasoning={"effort": "medium"},
        instructions=instructions,
        input=[{
            "role": "user",
            "content": [{"type": "text", "text": f"mode={mode}\nDOSSIÊ JSON:\n{dossier}"}]
        }]
    )
    return resp.output_text
