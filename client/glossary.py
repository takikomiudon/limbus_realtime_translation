"""client.glossary

Limbus Company glossary data used by Gemini prompts and Speech adaptation.
"""

GLOSSARY_TERMS = [
    ("림버스 컴퍼니", "Limbus Company", 20),
    ("이상", "イサン", 15),
    ("파우스트", "ファウスト", 15),
    ("돈 키호테", "ドンキホーテ", 15),
    ("료슈", "良秀", 15),
    ("뫼르소", "ムルソー", 15),
    ("홍루", "ホンル", 15),
    ("히스클리프", "ヒースクリフ", 15),
    ("이스마엘", "イシュメール", 15),
    ("로디온", "ロージャ", 15),
    ("싱클레어", "シンクレア", 15),
    ("아웃티스", "ウーティス", 15),
    ("그레고르", "グレゴール", 15),
    ("수감자", "囚人", 15),
    ("인격", "人格", 15),
    ("EGO", "EGO", 15),
    ("거울 던전", "鏡ダンジョン", 15),
    ("거울 굴절 철도", "鏡屈折鉄道", 15),
    ("발푸르기스의 밤", "ヴァルプルギスの夜", 15),
    ("흑수", "黒獣", 15),
    ("가주 후보", "家主候補", 15),
    ("레이혼", "レイホン", 15),
    ("지아·초우", "ジア・チォウ", 15),
    ("로보토미 코퍼레이션", "Lobotomy Corporation", 15),
    ("라이브러리 오브 루이나", "Library of Ruina(ラオル)", 15),
    ("티페리트", "ティファレト", 15),
    ("증오의 여왕", "憎しみの女王", 15),
    ("절망의 기사", "絶望の騎士", 15),
    ("탐욕의 왕", "貪欲の王", 15),
    ("분노의 시종", "憤怒の従者", 15),
    ("마법소녀", "魔法少女", 15),
    ("명일방주", "アークナイツ", 15),
]


def build_system_prompt() -> str:
    """Build the system instruction with glossary terms (no user text included)."""
    glossary = "\n".join(f"{source}: {target}" for source, target, _ in GLOSSARY_TERMS)
    return f"""あなたには韓国のソシャゲ、Limbus Companyのシーズン6のロードマップ説明放送の内容を日本語に翻訳してもらいます。
用語としては以下のようなものがあります。
{glossary}
これらの用語集を参考に韓国語の文章を日本語に翻訳してください。
翻訳結果以外は何も出力しないでください。"""


def speech_phrases() -> list[dict[str, object]]:
    """Return phrase-set entries for Google Speech adaptation."""
    return [{"value": source, "boost": boost} for source, _, boost in GLOSSARY_TERMS]
