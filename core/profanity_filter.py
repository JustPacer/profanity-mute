import re
from typing import List, Dict, Tuple, Set

class ProfanityFilter:
    """
    Детектор матерных и нецензурных слов для русского и английского языков.
    Использует юникод-границы слов и защищен от ложных срабатываний (ребята, себе, тебя и т.д.).
    """

    B_START = r'(?<![а-яеa-z0-9])'
    B_END   = r'(?![а-яеa-z0-9])'

    RUSSIAN_PROFANITY_PATTERNS = [
        # Корень хуй / хуе / хуя / хуи / хуин
        B_START + r'(?:[а-я]*х[уy][йяеиоюа][а-я]*)' + B_END,
        B_START + r'нах[уy][йяеин]' + B_END,
        B_START + r'пох[уy][йяеин]' + B_END,
        B_START + r'них[уy][йяеин]' + B_END,
        B_START + r'дох[уy][йяеин]' + B_END,
        B_START + r'зах[уy][йяеин]' + B_END,
        B_START + r'ох[уy]е[тльвшссйя]*' + B_END,

        # Корень пизд
        B_START + r'(?:[а-я]*п[иiе]зд[а-я]*)' + B_END,

        # Корень еб / ёб
        B_START + r'(?:ебат[ься]*|ебал[аоия]*|ебан[а-я]*|ебаш[а-я]*|ебуч[а-я]*|ебн[а-я]*|ебщ[а-я]*|ебану[тльвшссйя]*|ебальн[а-я]*|еблан[а-я]*)' + B_END,
        B_START + r'(?:[а-я]*(?:за|вы|на|до|по|про|раз|съ|от|пере|при|об|у|с|разъ|под|из)еб[а-я]*)' + B_END,
        B_START + r'долб[оае]*б[а-я]*' + B_END,
        B_START + r'уеб[оа-я]*' + B_END,
        B_START + r'ебать|ебал|ебала|ебали|ебанутый|ебанутая|ебнуть|ебнулся|ебнулась|ебальник' + B_END,

        # Бля / блядь / блят
        B_START + r'б[л]+я[тдтьдсжмвфкпроляью]*' + B_END,

        # Сука / сукин
        B_START + r'сук[аамиоуеиншчкз]*' + B_END,
        B_START + r'сучи[йяеоусмтч]*' + B_END,

        # Пидор / пидарас / пидорас
        B_START + r'п[иi]д[оау]р[а-я]*' + B_END,
        B_START + r'п[иi]д[оау]рас[а-я]*' + B_END,

        # Говно / говен
        B_START + r'говн[оауеыяинамямивт]*' + B_END,
        B_START + r'говн[яеию]*' + B_END,

        # Мудак / Мудило
        B_START + r'муд[ааоеиуыя]к[а-я]*' + B_END,
        B_START + r'муд[ииоае]л[а-я]*' + B_END,

        # Манда
        B_START + r'манд[а-я]*' + B_END,

        # Гандон / Кондон
        B_START + r'г[ао]нд[оа]н[а-я]*' + B_END,
    ]

    ENGLISH_PROFANITY_PATTERNS = [
        B_START + r'fuck[a-z]*' + B_END,
        B_START + r'motherfucker[a-z]*' + B_END,
        B_START + r'shit[a-z]*' + B_END,
        B_START + r'bitch[a-z]*' + B_END,
        B_START + r'cunt[a-z]*' + B_END,
        B_START + r'dick[a-z]*' + B_END,
        B_START + r'asshole[a-z]*' + B_END,
        B_START + r'pussy[a-z]*' + B_END,
        B_START + r'whore[a-z]*' + B_END,
        B_START + r'slut[a-z]*' + B_END,
    ]

    DEFAULT_WHITELIST = {
        'себе', 'себя', 'тебе', 'тебя', 'ребят', 'ребята', 'ребятки', 'ребятам', 'ребятами',
        'волшебные', 'волшебный', 'волшебная', 'волшебно', 'волшебство', 'неплохой', 'неплохо',
        'неплохая', 'неплохие', 'хлеб', 'хлеба', 'хлебом', 'хлебе', 'колебать', 'колебания',
        'колеблется', 'застраховать', 'страховать', 'страховка', 'оскорблять', 'оскорбления',
        'перелезать', 'заедать', 'заедает', 'рубль', 'рублей', 'скипидар', 'педаль', 'педали',
        'педагог', 'педагогика', 'потребить', 'употребить', 'сукно', 'сукном', 'сукна',
        'огребать', 'грести', 'гребля', 'употребление', 'потери', 'рубли', 'рублях',
        'гребешок', 'пособник', 'загребать', 'стебель', 'гребень', 'жребий', 'серебро',
        'лебедь', 'мебель', 'небо', 'небеса', 'небе', 'погреб', 'загреб', 'отгреб',
        'особенно', 'особенность', 'потребность', 'требовать', 'требование', 'требует'
    }

    def __init__(self, custom_bad_words: List[str] = None, custom_whitelist: List[str] = None):
        self.compiled_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in (self.RUSSIAN_PROFANITY_PATTERNS + self.ENGLISH_PROFANITY_PATTERNS)
        ]
        
        self.whitelist: Set[str] = set(self.DEFAULT_WHITELIST)
        if custom_whitelist:
            self.whitelist.update(w.lower().strip() for w in custom_whitelist)
            
        self.custom_bad_words: Set[str] = set()
        if custom_bad_words:
            self.custom_bad_words.update(w.lower().strip() for w in custom_bad_words if w.strip())

    @staticmethod
    def clean_word(word: str) -> str:
        """Очищает слово от знаков препинания и приподнимает ё -> е."""
        cleaned = re.sub(r'[^\w\s]', '', word, flags=re.UNICODE).lower().strip()
        return cleaned.replace('ё', 'е')

    def is_profane(self, raw_word: str) -> bool:
        word = self.clean_word(raw_word)
        if not word or len(word) < 2:
            return False

        if word in self.whitelist:
            return False

        if word in self.custom_bad_words:
            return True

        for pattern in self.compiled_patterns:
            if pattern.search(word):
                return True

        return False

    def find_profanity_in_segments(self, segments: List[Dict]) -> List[Dict]:
        profane_words = []

        for segment in segments:
            if hasattr(segment, 'words') and segment.words:
                words_list = segment.words
            elif isinstance(segment, dict) and 'words' in segment:
                words_list = segment['words']
            else:
                text = getattr(segment, 'text', '') or segment.get('text', '')
                clean_txt = self.clean_word(text)
                if self.is_profane(clean_txt):
                    start = getattr(segment, 'start', 0.0) or segment.get('start', 0.0)
                    end = getattr(segment, 'end', 0.0) or segment.get('end', 0.0)
                    profane_words.append({
                        'word': text,
                        'clean_word': clean_txt,
                        'start': start,
                        'end': end,
                        'probability': 1.0
                    })
                continue

            for word_obj in words_list:
                w_text = getattr(word_obj, 'word', '') or word_obj.get('word', '')
                clean_w = self.clean_word(w_text)
                
                if self.is_profane(clean_w):
                    start = getattr(word_obj, 'start', 0.0) or word_obj.get('start', 0.0)
                    end = getattr(word_obj, 'end', 0.0) or word_obj.get('end', 0.0)
                    prob = getattr(word_obj, 'probability', 1.0) or word_obj.get('probability', 1.0)
                    
                    profane_words.append({
                        'word': w_text.strip(),
                        'clean_word': clean_w,
                        'start': start,
                        'end': end,
                        'probability': prob
                    })

        return profane_words
