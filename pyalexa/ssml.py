PARAGRAPH = 'p'
SENTENCE = 's'
BREAK = 'b'
SAY_AS = 'say-as'
PHONEME = 'phoneme'
W = 'w'

class SSMLPart:
    def __init__(self, tag, contents=None, attrs={}, **kwargs):
        self._tag = tag
        self._contents = contents
        self._attrs = attrs
        self._attrs.update(kwargs)

    def __opentag(self):
        # TODO this will break if you have unescaped quotes
        return '<{0}{1}>'.format(self._tag, (' ' if self._attrs else '') + ' '.join(('{0}="{1}"'.format(k,v) for k,v in self._attrs.items() if v is not None)))

    def __str__(self):
        if self._contents is None:
            return '<{0}/>'.format(self.__opentag())
        else:
            return '{0}{1}</{2}>'.format(self.__opentag(), self._contents, self._tag)

    def __add__(self, other):
        return str(self) + str(other)

def plain(text):
    return text

def paragraph(text):
    return SSMLPart(PARAGRAPH, text)

def sentence(text):
    return SSMLPart(SENTENCE, text)

def p(*args, **kwargs):
    return paragraph(*args, **kwargs)

def s(*args, **kwargs):
    return sentence(*args, **kwargs)

def brk(strength=None, time=None):
    return SSMLPart(BREAK, strength=strength, time=time)

def say_as(text, interpret_as=None, format=None):
    return SSMLPart(SAY_AS, text, attrs={'interpret-as': interpret_as, 'format': format})

def phoneme(text, alphabet=None, ph=None):
    return SSMLPart(PHONEME, text, alphabet=alphabet, ph=ph)

def w(text, role=None):
    return SSMLPart(W, text, role=role)
