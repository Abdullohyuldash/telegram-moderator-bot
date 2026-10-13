from pathlib import Path
import re
from config import VIOLATION_TEXT

CUSTOM_WORDS_FILE = Path(__file__).resolve().parent / "custom_bad_words.txt"

# O'zbek tilidagi apostrof belgilarini yagona standartga keltirish jadvali
APOSTROPHE_CHARS = ("‘", "’", "`", "ʻ", "ʼ", "´", "ʹ")

# O'zbek lotin qo'shimchalari (o'zak so'kinish so'zlariga qo'shilishi mumkin bo'lgan shakllar)
UZ_LATIN_SUFFIXES: tuple[str, ...] = (
    "",
    "lar",
    "larni",
    "larga",
    "lardan",
    "larim",
    "laring",
    "ni",
    "ning",
    "ga",
    "da",
    "dan",
    "san",
    "siz",
    "man",
    "miz",
    "misan",
    "misiz",
    "mi",
    "ku",
    "chi",
    "im",
    "ing",
    "ingni",
    "ingga",
    "ingdan",
    "i",
    "si",
    "sini",
    "siga",
    "dek",
    "day",
    "roq",
)

# O'zbek kirill qo'shimchalari
UZ_CYRILLIC_SUFFIXES: tuple[str, ...] = (
    "",
    "лар",
    "ларни",
    "ларга",
    "лардан",
    "ни",
    "нинг",
    "га",
    "да",
    "дан",
    "сан",
    "сиз",
    "ман",
    "мисан",
    "мисиз",
    "ми",
    "ку",
    "чи",
    "им",
    "инг",
    "ингни",
    "ингга",
    "ингдан",
    "и",
    "си",
    "сини",
    "сига",
    "дек",
    "дай",
)

# 1. O'zbekcha lotincha aniq o'zak so'kinishlar (qo'shimchalar bilan avtomatik boyitiladi)
UZ_LATIN_ROOTS: set[str] = {
    "jalab",
    "jalap",
    "jallab",
    "qotoq",
    "qo'toq",
    "qutoq",
    "qotoqbosh",
    "qo'toqbosh",
    "qutoqbosh",
    "qotog'",
    "qo'tog'",
    "qutog'",
    "ko'tak",
    "kotak",
    "ko'toq",
    "ambosh",
    "sikay",
    "sikaman",
    "sikish",
    "siktir",
    "sikib",
    "sikdi",
    "sikilgan",
    "sikyapti",
    "siksin",
    "gandon",
    "gondon",
    "haromi",
    "xaromi",
    "haromzada",
    "xaromzada",
    "foxisha",
    "fohisha",
    "sharmanda",
    "iflos",
    "maraz",
    "benomus",
    "dayus",
    "hezalak",
    "xezalak",
    "xunasa",
    "hunasa",
    "itvachcha",
    "itwachcha",
    "dalbayob",
    "dalbayop",
    "dolboyob",
    "dolbayob",
    "pidaraz",
    "pidaras",
    "pidr",
    "pedik",
    "chmo",
    "chmoshnik",
    "sucka",
    "suchka",
    "shlyuxa",
    "shluha",
    "shalava",
    "mudak",
    "gavno",
    "govno",
}

# Qisqa yoki boshqa so'zlar bilan adashishi mumkin bo'lgan o'zbekcha lotin so'zlarning FAQAT aniq shakllari
UZ_LATIN_EXACT: set[str] = {
    "am",
    "aming",
    "amingni",
    "amingga",
    "amingdan",
    "amlar",
    "amlarni",
    "amini",
    "amiga",
    "amsan",
    "sik",
    "sikdim",
    "sikding",
    "sikishdi",
    "sikkir",
    "ko't",
    "kot",
    "ko'tsan",
    "kotsan",
    "ko'ting",
    "koting",
    "ko'tingni",
    "kotingni",
    "ko'tingga",
    "kotingga",
    "ko'tingdan",
    "kotingdan",
    "ko'tlar",
    "kotlar",
    "ko'tlarni",
    "kotlarni",
    "ko'ti",
    "ko'tini",
    "koti",
    "kotini",
    "onangni",
    "onangdi",
    "ayangni",
    "opangni",
    "singlingni",
    "otangni",
    "padaringga",
    "padaringa",
}

# 2. O'zbekcha kirillcha aniq o'zak so'kinishlar (qo'shimchalar bilan avtomatik boyitiladi)
UZ_CYRILLIC_ROOTS: set[str] = {
    "жалаб",
    "жалап",
    "жаллаб",
    "қўтоқ",
    "қотоқ",
    "қутоқ",
    "қўтоқбош",
    "қотоқбош",
    "қутоқбош",
    "қўтоғ",
    "қотоғ",
    "қутоғ",
    "кўтак",
    "котак",
    "амбош",
    "сикай",
    "сикаман",
    "сикиш",
    "сиктир",
    "сикиб",
    "сикди",
    "сикилган",
    "сикяпти",
    "сиксин",
    "гандон",
    "гондон",
    "ҳароми",
    "хароми",
    "ҳаромзада",
    "харомзада",
    "фоҳиша",
    "фохиша",
    "шарманда",
    "ифлос",
    "мараз",
    "беномус",
    "даюс",
    "ҳезалак",
    "хезалак",
    "хунаса",
    "итвачча",
    "далбаёб",
    "далбаёп",
    "долбоёб",
    "долбаёб",
    "пидараз",
    "пидарас",
    "пидр",
    "чмо",
    "чмошник",
}

UZ_CYRILLIC_EXACT: set[str] = {
    "ам",
    "аминг",
    "амингни",
    "амингга",
    "амингдан",
    "амини",
    "амига",
    "амлар",
    "амсан",
    "сик",
    "сикдим",
    "сикдинг",
    "сиккир",
    "кўт",
    "кўтсан",
    "кўтинг",
    "кўтингни",
    "кўтингга",
    "кўтингдан",
    "кўти",
    "кўтини",
    "кўтлар",
    "кўтларни",
    "онангни",
    "онангди",
    "опангни",
    "синглингни",
    "падарингга",
}

# 3. Ruscha kirillcha ochiq so'kinish so'zlar to'plami (mat va haqoratlar)
RU_CYRILLIC_BAD_WORDS: set[str] = {
    "хуй",
    "хуя",
    "хую",
    "хуем",
    "хуе",
    "хуи",
    "хуев",
    "хуям",
    "хуями",
    "хуях",
    "хуйня",
    "хуйни",
    "хуйне",
    "хуйню",
    "хуйней",
    "хуесос",
    "хуесосы",
    "хуесоса",
    "хуевый",
    "хуёвый",
    "хуево",
    "хуёво",
    "хуета",
    "хуетень",
    "охуеть",
    "охуел",
    "охуела",
    "охуели",
    "охуенно",
    "охуенный",
    "охуевший",
    "ахуеть",
    "ахуел",
    "ахуела",
    "ахуели",
    "нахуй",
    "нахуя",
    "похуй",
    "похую",
    "нехуй",
    "дохуя",
    "нихуя",
    "отхуярить",
    "пизда",
    "пизды",
    "пизде",
    "пизду",
    "пиздой",
    "пиздец",
    "пиздеца",
    "пиздеть",
    "пиздишь",
    "пиздит",
    "пиздят",
    "пиздел",
    "пиздюк",
    "пиздюки",
    "пиздюлей",
    "пиздюлина",
    "пиздабол",
    "пиздаболы",
    "пиздатый",
    "пиздато",
    "пиздень",
    "распиздяй",
    "спиздить",
    "спиздил",
    "отпиздить",
    "выпиздить",
    "ебать",
    "ебал",
    "ебала",
    "ебали",
    "ебут",
    "ебет",
    "ебёт",
    "ебешь",
    "ебёшь",
    "ебаный",
    "ёбаный",
    "ебаная",
    "ёбаная",
    "ебаное",
    "ёбаное",
    "ебаные",
    "ёбаные",
    "ебальник",
    "ебало",
    "ебло",
    "еблан",
    "ебланы",
    "еблана",
    "ебанат",
    "ебанутый",
    "ебанутая",
    "ебануться",
    "ебанулся",
    "заебал",
    "заебала",
    "заебали",
    "заебать",
    "заебись",
    "заебок",
    "выебал",
    "выебать",
    "выебон",
    "уебок",
    "уёбок",
    "уебки",
    "уёбки",
    "уебан",
    "уебать",
    "уебал",
    "съебаться",
    "съебись",
    "съебал",
    "отъебись",
    "разъебать",
    "проебать",
    "проебал",
    "наебать",
    "наебал",
    "долбоеб",
    "долбоёб",
    "долбоебы",
    "долбоёбы",
    "долбоебизм",
    "блядь",
    "блять",
    "бля",
    "бляди",
    "блядей",
    "блядина",
    "блядство",
    "блядский",
    "сука",
    "суки",
    "суку",
    "сукой",
    "сучка",
    "сучки",
    "сучара",
    "сученыш",
    "пидор",
    "пидоры",
    "пидора",
    "пидорас",
    "пидорасы",
    "пидарас",
    "пидарасы",
    "пидрила",
    "пидорский",
    "педик",
    "педики",
    "педераст",
    "гандон",
    "гандоны",
    "гондон",
    "гондоны",
    "шлюха",
    "шлюхи",
    "шлюху",
    "шлюхой",
    "проститутка",
    "проститутки",
    "шалава",
    "шалавы",
    "шмара",
    "мразь",
    "мрази",
    "мразота",
    "тварь",
    "твари",
    "мудак",
    "мудаки",
    "мудака",
    "мудило",
    "мудила",
    "мудозвон",
    "дрочить",
    "дрочил",
    "дрочила",
    "дрочер",
    "залупа",
    "залупы",
    "манда",
    "манды",
    "мандавошка",
    "елда",
    "жопа",
    "говно",
    "гавно",
    "дерьмо",
    "гнида",
    "гниды",
    "падла",
    "ублюдок",
    "ублюдки",
    "выродок",
    "дебил",
    "дебилы",
    "даун",
    "кретин",
    "идиот",
    "урод",
    "уроды",
    "скотина",
}

# 4. Ruscha lotin (translit) ochiq so'kinish so'zlar to'plami
RU_TRANSLIT_BAD_WORDS: set[str] = {
    "xuy",
    "huy",
    "xuya",
    "huya",
    "xuynya",
    "huynya",
    "xuesos",
    "huesos",
    "xueviy",
    "hueviy",
    "naxuy",
    "nahuy",
    "naxuya",
    "nahuya",
    "poxuy",
    "pohuy",
    "neXuy",
    "nehuy",
    "oxuet",
    "ohuet",
    "oxuel",
    "ohuel",
    "axuet",
    "ahuet",
    "axuel",
    "ahuel",
    "pizda",
    "pizdi",
    "pizdy",
    "pizdec",
    "pizdets",
    "pizdu",
    "pizduk",
    "pizdyuk",
    "pizdabol",
    "pizdet",
    "pizdish",
    "spizdil",
    "ebat",
    "yebat",
    "ebal",
    "yebal",
    "ebali",
    "yebali",
    "ebaniy",
    "yebaniy",
    "ebanaya",
    "yebanaya",
    "ebalo",
    "yebalo",
    "eblan",
    "yeblan",
    "eblani",
    "ebanat",
    "ebanutiy",
    "zaebal",
    "zayebal",
    "zaebala",
    "zaebali",
    "zayebali",
    "zaebis",
    "zayebis",
    "uebok",
    "uyebok",
    "uebki",
    "ueban",
    "uyeban",
    "otebis",
    "syebis",
    "dolboeb",
    "dolboyob",
    "dolbayob",
    "blyad",
    "blyat",
    "blat",
    "blya",
    "blyadina",
    "suka",
    "suki",
    "suchka",
    "suchara",
    "pidor",
    "pidori",
    "pidoras",
    "pidaras",
    "pidrila",
    "pedik",
    "gandon",
    "gondon",
    "shlyuxa",
    "shlyuha",
    "shluxa",
    "shluha",
    "shalava",
    "prostitutka",
    "shmara",
    "mudak",
    "mudila",
    "zalupa",
    "mraz",
    "mrazota",
    "tvar",
    "ublyudok",
    "gnida",
    "padla",
    "govno",
    "gavno",
    "dermo",
    "drochit",
    "drocher",
}


def _build_expanded_bad_words() -> set[str]:
    """O'zak so'zlarga o'zbek/rus qo'shimchalarini qo'shib to'liq lug'atni shakllantiradi."""
    words: set[str] = set()

    for root in UZ_LATIN_ROOTS:
        for suffix in UZ_LATIN_SUFFIXES:
            words.add(f"{root}{suffix}")

    for root in UZ_CYRILLIC_ROOTS:
        for suffix in UZ_CYRILLIC_SUFFIXES:
            words.add(f"{root}{suffix}")

    words |= UZ_LATIN_EXACT
    words |= UZ_CYRILLIC_EXACT
    words |= RU_CYRILLIC_BAD_WORDS
    words |= RU_TRANSLIT_BAD_WORDS

    if CUSTOM_WORDS_FILE.exists():
        for line in CUSTOM_WORDS_FILE.read_text(encoding="utf-8").splitlines():
            cleaned = line.strip().lower()
            if not cleaned or cleaned.startswith("#"):
                continue
            for ch in APOSTROPHE_CHARS:
                cleaned = cleaned.replace(ch, "'")
            words.add(cleaned)
            # Agar so'z 4 harfdan uzun bo'lsa, qo'shimchalarini ham qo'shamiz
            if len(cleaned) >= 4:
                is_cyrillic = any("а" <= c <= "я" or c in "ўқғҳё" for c in cleaned)
                suffixes = UZ_CYRILLIC_SUFFIXES if is_cyrillic else UZ_LATIN_SUFFIXES
                for suffix in suffixes:
                    words.add(f"{cleaned}{suffix}")

    return words


BAD_WORDS_SET: set[str] = _build_expanded_bad_words()

# So'zlarni ajratib olish uchun regulyar ifoda (harflar, raqamlar va so'z ichidagi apostrof)
WORD_TOKEN_PATTERN = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)*", re.UNICODE)


def reload_bad_words() -> int:
    """custom_bad_words.txt faylidan so'zlarni qayta yuklaydi va jami so'zlar sonini qaytaradi."""
    global BAD_WORDS_SET
    BAD_WORDS_SET = _build_expanded_bad_words()
    return len(BAD_WORDS_SET)


def add_custom_bad_words(new_words: list[str]) -> list[str]:
    """
    Yangi taqiqlangan so'zlarni filters/custom_bad_words.txt fayliga saqlaydi
    va xotiradagi BAD_WORDS_SET to'plamini darhol yangilaydi.
    """
    added: list[str] = []
    existing_lines: set[str] = set()
    if CUSTOM_WORDS_FILE.exists():
        existing_lines = {
            line.strip().lower()
            for line in CUSTOM_WORDS_FILE.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        }

    with CUSTOM_WORDS_FILE.open("a", encoding="utf-8") as f:
        for raw_word in new_words:
            word = raw_word.strip().lower()
            for ch in APOSTROPHE_CHARS:
                word = word.replace(ch, "'")
            if word and word not in existing_lines:
                f.write(f"\n{word}")
                existing_lines.add(word)
                added.append(word)

    reload_bad_words()
    return added


def tokenize_text(text: str) -> set[str]:
    """
    Matnni kichik harflarga o'tkazadi, apostroflarni standartlashtiradi,
    tinish belgilarini olib tashlab, alohida so'zlar to'plamiga (set) ajratadi.
    """
    normalized = text.lower()
    for ch in APOSTROPHE_CHARS:
        normalized = normalized.replace(ch, "'")

    return set(WORD_TOKEN_PATTERN.findall(normalized))


def check_text(text: str | None) -> str | None:
    """
    Matn ichida qora ro'yxatdagi so'kinish so'zlari bor-yo'qligini tekshiradi.
    Agar kesishma (intersection) topilsa -> VIOLATION_TEXT qaytaradi, aks holda None.
    """
    if not text or not text.strip():
        return None

    words_set = tokenize_text(text)
    if words_set.intersection(BAD_WORDS_SET):
        return VIOLATION_TEXT

    return None
