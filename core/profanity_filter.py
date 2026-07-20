import re
from typing import List, Dict, Tuple, Set

class ProfanityFilter:
    """
    Детектор матерных и нецензурных слов для русского и английского языков.
    Поддерживает вычисление границ корня слова (Root-only muting).
    """

    B_START = r'(?<![а-яеa-z0-9])'
    B_END   = r'(?![а-яеa-z0-9])'

    RUSSIAN_PROFANITY_PATTERNS = [
        # Корень хуй / хуе / хуя / хуи / хуин
        (B_START + r'(?:[а-я]*х[уy][йяеиоюа][а-я]*)' + B_END, r'х[уy][йяеиоюа]'),
        (B_START + r'нах[уy][йяеин]' + B_END, r'х[уy][йяеин]'),
        (B_START + r'пох[уy][йяеин]' + B_END, r'х[уy][йяеин]'),
        (B_START + r'них[уy][йяеин]' + B_END, r'х[уy][йяеин]'),
        (B_START + r'дох[уy][йяеин]' + B_END, r'х[уy][йяеин]'),
        (B_START + r'зах[уy][йяеин]' + B_END, r'х[уy][йяеин]'),
        (B_START + r'ох[уy]е[тльвшссйя]*' + B_END, r'х[уy]е'),

        # Корень пизд
        (B_START + r'(?:[а-я]*п[иiе]зд[а-я]*)' + B_END, r'п[иiе]зд'),

        # Корень еб / ёб
        (B_START + r'(?:ебат[ься]*|ебал[аоия]*|ебан[а-я]*|ебаш[а-я]*|ебуч[а-я]*|ебн[а-я]*|ебщ[а-я]*|ебану[тльвшссйя]*|ебальн[а-я]*|еблан[а-я]*)' + B_END, r'еб'),
        (B_START + r'(?:[а-я]*(?:за|вы|на|до|по|про|раз|съ|от|пере|при|об|у|с|разъ|под|из)еб[а-я]*)' + B_END, r'еб'),
        (B_START + r'долб[оае]*б[а-я]*' + B_END, r'е?б'),
        (B_START + r'уеб[оа-я]*' + B_END, r'е?б'),
        (B_START + r'ебать|ебал|ебала|ебали|ебанутый|ебанутая|ебнуть|ебнулся|ебнулась|ебальник' + B_END, r'еб'),

        # Бля / блядь / блят
        (B_START + r'б[л]+я[тдтьдсжмвфкпроляью]*' + B_END, r'б[л]+я'),

        # Сука / сукин
        (B_START + r'сук[аамиоуеиншчкз]{1,4}' + B_END, r'сук'),
        (B_START + r'сучи[йяеоусмтч]*' + B_END, r'суч'),

        # Пидор / пидарас / пидорас
        (B_START + r'п[иi]д[оау]р[а-я]*' + B_END, r'п[иi]д[оау]р'),
        (B_START + r'п[иi]д[оау]рас[а-я]*' + B_END, r'п[иi]д[оау]рас'),

        # Говно / говен
        (B_START + r'говн[оауеыяинамямивт]*' + B_END, r'говн'),

        # Мудак / Мудило
        (B_START + r'муд[ааоеиуыя]к[а-я]*' + B_END, r'муд'),

        # Манда
        (B_START + r'манд[а-я]*' + B_END, r'манд'),

        # Гандон / Кондон
        (B_START + r'г[ао]нд[оа]н[а-я]*' + B_END, r'г[ао]нд[оа]н'),
    ]

    ENGLISH_PROFANITY_PATTERNS = [
        (B_START + r'fuck[a-z]*' + B_END, r'fuck'),
        (B_START + r'motherfucker[a-z]*' + B_END, r'fucker'),
        (B_START + r'shit[a-z]*' + B_END, r'shit'),
        (B_START + r'bitch[a-z]*' + B_END, r'bitch'),
        (B_START + r'cunt[a-z]*' + B_END, r'cunt'),
        (B_START + r'dick[a-z]*' + B_END, r'dick'),
        (B_START + r'asshole[a-z]*' + B_END, r'asshole'),
        (B_START + r'pussy[a-z]*' + B_END, r'pussy'),
        (B_START + r'whore[a-z]*' + B_END, r'whore'),
        (B_START + r'slut[a-z]*' + B_END, r'slut'),
    ]

    DEFAULT_WHITELIST = {
        'сухую', 'сухой', 'сухая', 'сухого', 'сухих', 'сухие', 'сухость', 'засуха', 'суша',
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
            (re.compile(pat, re.IGNORECASE), root_pat)
            for pat, root_pat in (self.RUSSIAN_PROFANITY_PATTERNS + self.ENGLISH_PROFANITY_PATTERNS)
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

    def find_root_bounds(self, clean_w: str, start: float, end: float) -> Tuple[float, float]:
        """
        Вычисляет точные границы времени корня матерного слова (Root-only muting).
        Пример: для "заебался" (0.8с) вернет только отрезок произношения "-еб-".
        """
        duration = max(0.1, end - start)
        n_chars = len(clean_w)
        if n_chars <= 3:
            # Для коротких слов (хуй, бля) заглушаем 80% слова
            return start + (duration * 0.1), end - (duration * 0.1)

        root_start_idx = 0
        root_end_idx = n_chars

        for pattern, root_regex in self.compiled_patterns:
            match = pattern.search(clean_w)
            if match:
                root_match = re.search(root_regex, match.group(0), re.IGNORECASE)
                if root_match:
                    root_start_idx = match.start() + root_match.start()
                    root_end_idx = match.start() + root_match.end()
                    break

        # Вычисляем относительные доли времени
        r_start_frac = max(0.0, root_start_idx / n_chars)
        r_end_frac = min(1.0, root_end_idx / n_chars)

        # Гарантируем минимальную длительность глушения корня (не менее 0.15с)
        calc_start = start + (duration * r_start_frac)
        calc_end = start + (duration * r_end_frac)

        if (calc_end - calc_start) < 0.15:
            center = (calc_start + calc_end) / 2.0
            calc_start = max(start, center - 0.08)
            calc_end = min(end, center + 0.08)

        return calc_start, calc_end

    def is_profane(self, raw_word: str) -> bool:
        word = self.clean_word(raw_word)
        if not word or len(word) < 2:
            return False

        if word in self.whitelist:
            return False

        if word in self.custom_bad_words:
            return True

        for pattern, _ in self.compiled_patterns:
            if pattern.search(word):
                return True

        return False

    def find_profanity_in_segments(self, segments: List[Dict], root_only: bool = True) -> List[Dict]:
        """
        Ищет нецензурные слова. Если root_only=True, рассчитывает границы корня слова.
        """
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
                    
                    r_start, r_end = self.find_root_bounds(clean_txt, start, end) if root_only else (start, end)
                    profane_words.append({
                        'word': text,
                        'clean_word': clean_txt,
                        'start': r_start,
                        'end': r_end,
                        'full_start': start,
                        'full_end': end,
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
                    
                    r_start, r_end = self.find_root_bounds(clean_w, start, end) if root_only else (start, end)

                    profane_words.append({
                        'word': w_text.strip(),
                        'clean_word': clean_w,
                        'start': r_start,
                        'end': r_end,
                        'full_start': start,
                        'full_end': end,
                        'probability': prob
                    })

        return profane_words
