import urllib3
import re

http = urllib3.PoolManager()

bad_word_list = None
SPECIAL_CHARS = re.compile(r'[^a-zA-Z0-9]')

def fetch_bad_word_list():
    output = []
    uri = f"https://raw.githubusercontent.com/coffee-and-fun/google-profanity-words/refs/heads/main/data/en.txt"
    response = http.request(
        "GET",
        uri,
        headers={},
    )
    for line in response.data.splitlines():
        bad_word = line.decode('utf-8').strip()
        if 'e' in bad_word:
            bad_word = bad_word.replace('e', '[e3]')
        if 'g' in bad_word:
            bad_word = bad_word.replace('g', '[g9]')
        if 'i' in bad_word:
            bad_word = bad_word.replace('i', '[i1]')
        if 'o' in bad_word:
            bad_word = bad_word.replace('o', '[o0]')
        if 's' in bad_word:
            bad_word = bad_word.replace('s', '[s5]')
        if 't' in bad_word:
            bad_word = bad_word.replace('t', '[t7]')
        output.append(re.compile(bad_word))

    return output

def has_bad_word(input_text):
    global bad_word_list
    if not bad_word_list:
        bad_word_list = fetch_bad_word_list()
    input_text = re.sub(SPECIAL_CHARS, '', input_text)
    return any(re.match(bad_word, input_text) for bad_word in bad_word_list)


if __name__ == '__main__':
    # Unit testing here, not committing
    # the tests for obvious reasons...
    pass