import re
from typing import List, Dict, Tuple, Set

class ProfanityFilter:
    """
    Детектор матерных и нецензурных слов для русского и английского языков.
    Поддерживает вычисление границ корня слова (Root-only muting) и расширенный белый список.
    """

    B_START = r'(?<![а-яеa-z0-9])'
    B_END   = r'(?![а-яеa-z0-9])'

    RUSSIAN_PROFANITY_PATTERNS = [
        # Корень хуй / хуе / хуя / хуи / хуин / хуяр / хуяч
        (B_START + r'(?:[а-я]*х[уy][йяеиоюаё][а-я]*)' + B_END, r'х[уy][йяеиоюаё]'),
        (B_START + r'нах[уy][йяеин]' + B_END, r'х[уy][йяеин]'),
        (B_START + r'пох[уy][йяеин]' + B_END, r'х[уy][йяеин]'),
        (B_START + r'них[уy][йяеин]' + B_END, r'х[уy][йяеин]'),
        (B_START + r'дох[уy][йяеин]' + B_END, r'х[уy][йяеин]'),
        (B_START + r'зах[уy][йяеин]' + B_END, r'х[уy][йяеин]'),
        (B_START + r'прох[уy][йя]' + B_END, r'х[уy][йя]'),
        (B_START + r'вх[уy]й' + B_END, r'х[уy]й'),
        (B_START + r'ух[уy]е[а-я]*' + B_END, r'х[уy]е'),
        (B_START + r'ох[уy]е[тльвшссйя]*' + B_END, r'х[уy]е'),
        (B_START + r'ох[уy]и[а-я]*' + B_END, r'х[уy]и'),
        (B_START + r'х[уy]л[иь]' + B_END, r'х[уy]л'),
        (B_START + r'х[уy]яр[а-я]*' + B_END, r'х[уy]яр'),
        (B_START + r'х[уy]яч[а-я]*' + B_END, r'х[уy]яч'),
        (B_START + r'х[уy]як[а-я]*' + B_END, r'х[уy]як'),
        (B_START + r'х[уy]ес[а-я]*' + B_END, r'х[уy]ес'),

        # Корень пизд / пёзд
        (B_START + r'(?:[а-я]*п[иiеё]зд[а-я]*)' + B_END, r'п[иiеё]зд'),
        (B_START + r'пиздяк[а-я]*' + B_END, r'пиздяк'),
        (B_START + r'пиздак[а-я]*' + B_END, r'пиздак'),
        (B_START + r'пиздан[а-я]*' + B_END, r'пиздан'),
        (B_START + r'пиздёнок[а-я]*' + B_END, r'пиздёнок'),
        (B_START + r'пиздолиз[а-я]*' + B_END, r'пиздолиз'),

        # Корень еб / ёб
        (B_START + r'(?:ебат[ься]*|ёбат[ься]*|ебал[аоия]*|ебан[а-я]*|ёбан[а-я]*|ебаш[а-я]*|ёбаш[а-я]*|ебуч[а-я]*|ёбуч[а-я]*|ебн[а-я]*|ёбн[а-я]*|ебщ[а-я]*|ебану[тльвшссйя]*|ебальн[а-я]*|еблан[а-я]*|ёбырь[а-я]*|ебырь[а-я]*)' + B_END, r'[её]б'),
        (B_START + r'(?:[а-я]*(?:за|на|вы|по|пере|раз|разъ|от|отъ|до|в|въ|у|съ|с)еб[а-я]*)' + B_END, r'еб'),
        (B_START + r'(?:[а-я]*(?:за|на|вы|по|пере|раз|разъ|от|отъ|до|в|въ|у|съ|с)ёб[а-я]*)' + B_END, r'ёб'),
        (B_START + r'долб[оае]*[её]б[а-я]*' + B_END, r'[её]?б'),
        (B_START + r'выебон[а-я]*' + B_END, r'еб'),

        # Трах (без слова "страх")
        (B_START + r'(?<!с)трах[а-я]*' + B_END, r'трах'),
        (B_START + r'затрах[а-я]*' + B_END, r'трах'),

        # Бля / блядь / блят / блядск / блядун / бляха
        (B_START + r'б[л]+я[тдтьдсжмвфкпроляью]*' + B_END, r'б[л]+я'),
        (B_START + r'блядск[а-я]*' + B_END, r'бляд'),
        (B_START + r'блядство' + B_END, r'бляд'),
        (B_START + r'блядун[а-я]*' + B_END, r'бляд'),
        (B_START + r'бляха[а-я]*' + B_END, r'бля'),

        # Сука / сучки / сучара
        (B_START + r'сук[аамиоуеиншчкз]{1,4}' + B_END, r'сук'),
        (B_START + r'сучи[йяеоусмтч]*' + B_END, r'суч'),
        (B_START + r'сучар[а-я]*' + B_END, r'суч'),

        # Мудак / Мудачьё / Мудозвон
        (B_START + r'муд[ааоеиуыя]к[а-я]*' + B_END, r'муд'),
        (B_START + r'мудачь[ёе]' + B_END, r'муд'),
        (B_START + r'мудил[а-я]*' + B_END, r'муд'),
        (B_START + r'мудозвон[а-я]*' + B_END, r'муд'),
        (B_START + r'мудоход[а-я]*' + B_END, r'муд'),

        # Залупа / Залуп
        (B_START + r'залуп[а-я]*' + B_END, r'залуп'),

        # Шлюха / Шлюх
        (B_START + r'шлюх[а-я]*' + B_END, r'шлюх'),

        # Манда
        (B_START + r'манд[а-я]*' + B_END, r'манд'),

        # Гандон / Кондон
        (B_START + r'г[ао]нд[оа]н[а-я]*' + B_END, r'г[ао]нд[оа]н'),

        # Ёпт / Ёпрст / Ётить
        (B_START + r'ёпт[а-я]*' + B_END, r'ёпт'),
        (B_START + r'ёпрст[а-я]*' + B_END, r'ёпрст'),
        (B_START + r'ётит[ься]*' + B_END, r'ётит'),

        # Пидор / Педик / Пидарас
        (B_START + r'п[иi]д[оау]р[а-я]*' + B_END, r'п[иi]д[оау]р'),
        (B_START + r'п[иi]д[оау]рас[а-я]*' + B_END, r'п[иi]д[оау]рас'),
        (B_START + r'педик[а-я]*' + B_END, r'педик'),

        # Дрочь / Дрочить / Кончать (с проверкой исключений "кончились")
        (B_START + r'дроч[а-я]*' + B_END, r'дроч'),

        # Даун / Додик (с проверкой исключений "нокдаун", "кулдаун")
        (B_START + r'додик[а-я]*' + B_END, r'додик'),
        (B_START + r'(?<!к)даун[а-я]*' + B_END, r'даун'),
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
        # Исключения даун
        'нокдаун', 'нокдауна', 'нокдауну', 'нокдауном', 'нокдауне', 'нокдауны', 'нокдаунов',
        'кулдаун', 'кулдауна', 'кулдауну', 'кулдауном', 'кулдауне', 'кулдауны', 'кулдаунов',
        'бэшдаун', 'башдаун', 'хулдаун', 'клудаун',

        # Исключения страх
        'страх', 'страха', 'страхе', 'страхи', 'страхом', 'страху', 'страхов',

        # Исключения кончать
        'кончились', 'кончилась', 'кончилось', 'кончился', 'кончаются', 'кончается', 'кончится', 'кончись', 'кончиться',

        # Исключения хулиган
        'хулиган', 'хулигана', 'хулигану', 'хулиганом', 'хулиганы', 'хулиганов', 'хулиганить', 'хулиганство',

        # Исключения редких слов и игровых терминов
        'трижды', 'употреблять', 'команда', 'команды', 'перебиваешь', 'перебивать', 'волшебницы',
        'реализовывать', 'ребутал', 'ребатл', 'ребаттл', 'перебаф', 'перебаффы', 'перебав',

        # Общеязыковые слова (защита от ложных срабатываний)
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
        'особенно', 'особенность', 'потребность', 'требовать', 'требование', 'требует',
        'истребить', 'истребление', 'истребитель'
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

        r_start_frac = max(0.0, root_start_idx / n_chars)
        r_end_frac = min(1.0, root_end_idx / n_chars)

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
