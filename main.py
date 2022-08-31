import requests
import time
import re
import datetime

TOKEN = ""
TIMEOUT = 60 * 5
VKpath = "https://api.vk.com/method/"
access_token = ""
v = "5.122"


def log(text):
    print("[{}] {}".format(datetime.datetime.now().strftime("%X"), text))


class InputMediaPhoto:
    def __init__(self, media, caption=None):
        self.type = 'photo'
        self.media = media
        self.caption = None

    def to_json(self):
        res_full = {'type': self.type,
                    'media': self.media,
                    'caption': self.caption}
        res = {}
        for key in res_full.keys():
            if res_full[key] is not None:
                res[key] = res_full[key]
        return res


class Update:
    def __init__(self, json_obj):
        self.update_id = json_obj['update_id']
        self.chat_id = json_obj['message']['chat']['id']
        if 'text' in json_obj['message']:
            self.text = json_obj['message']['text']
        else:
            self.text = None


class Telebot:
    def __init__(self, token, offset=None, timeout=None):
        self.token = token
        self.offset = offset
        self.timeout = timeout

    def make_request(self, method_name, params):
        path = "https://api.telegram.org/bot" + self.token + "/" + method_name
        new_params = {}
        for key in params.keys():
            if params[key] is not None:
                new_params[key] = params[key]
        params = new_params
        resp = requests.get(path, json=params)
        if resp.status_code != 200:
            log(resp.json())
            raise ConnectionError("Не удалось получить ответ от сервера.")
        if resp.json()['ok'] == False:
            raise ConnectionError("Неправильный запрос.")
        return resp.json()['result']

    def send_message(self, chat_id, text):
        method_name = r"sendMessage"
        params = {'chat_id': chat_id,
                  'text': text}
        self.make_request(method_name, params)

    def send_photo(self, chat_id, photoURL):
        method_name = r"sendPhoto"
        params = {'chat_id': chat_id,
                  'photo': photoURL}
        self.make_request(method_name, params)

    def send_media_group(self, chat_id, media):
        method_name = r"sendMediaGroup"
        media = list(map(InputMediaPhoto.to_json, media))
        params = {'chat_id': chat_id,
                  'media': media}
        self.make_request(method_name, params)

    def get_updates(self, offset=None, timeout=None, allowed_updates=['message']):
        method_name = r"getUpdates"
        if offset is None:
            offset = self.offset
        if timeout is None:
            timeout = self.timeout
        params = {'offset': offset,
                  'timeout': timeout,
                  'allowed_updates': allowed_updates}
        updates = self.make_request(method_name, params)
        updates = list(map(Update, updates))
        if len(updates) != 0:
            self.offset = updates[-1].update_id + 1
        return updates


class Meme:
    def __init__(self, json_meme):
        self.date = json_meme['date']
        self.text = json_meme['text']
        if 'copy_history' in json_meme:
            json_meme = json_meme['copy_history'][0]
            if self.text != "":
                self.text += "\n"
            self.text += json_meme['text']
        self.photos = []
        if 'attachments' in json_meme:
            for json_photo in json_meme['attachments']:
                if json_photo['type'] == 'photo':
                    self.photos.append(json_photo['photo']['sizes'][-1]['url'])

    def send(self, chat_id):
        if len(self.photos) == 0:
            bot.send_message(chat_id=chat_id, text=self.text)
        if len(self.photos) > 0:
            media = list(map(InputMediaPhoto, self.photos))
            media[0].caption = self.text
            bot.send_media_group(chat_id=chat_id, media=media)

    def __lt__(self, other):
        return self.date < other.date


def wall_get(group_id, count=100):
    resp = requests.get(VKpath+"wall.get", {'owner_id': -group_id,
                                            'count': count,
                                            'filter': 'owner',
                                            'access_token': access_token,
                                            'v': v})
    if resp.status_code != 200:
        raise ConnectionError
    if 'error' in resp.json():
        log(resp.json()['error']['error_msg'])
        raise ConnectionError
    meme_list = list(map(Meme, resp.json()['response']['items']))
    meme_list.sort()
    return meme_list


class Group:
    def __init__(self, group_id=None):
        global access_token
        global v
        if group_id is None:
            return
        resp = requests.get(VKpath+"groups.getById", {'group_id': group_id,
                                                      'access_token': access_token,
                                                      'v': v})
        if resp.status_code != 200:
            log("Не удалось подключиться к сети.")
            raise ConnectionError
        if 'error' in resp.json():
            log("Непраильный аргумент.")
            raise AttributeError
        self.group_id = resp.json()['response'][0]['id']
        self.name = resp.json()['response'][0]['name']
        memes_list = wall_get(self.group_id, 5)
        self.last_meme_date = memes_list[-1].date

    def __lt__(self, other):
        return self.name < other.name

    def __eq__(self, other):
        return self.group_id == other.group_id

    def __str__(self):
        return "{}\n{}\n{}\n".format(self.group_id, self.name, self.last_meme_date)


def read_group(fin):
    res = Group()
    res.group_id = int(fin.readline())
    res.name = fin.readline()[:-1]
    res.last_meme_date = int(fin.readline())
    return res


def update_groups():
    log("Обновление групп.")
    global users_list
    for user in users_list:
        for group in user.groups_list:
            memes_list = wall_get(group.group_id)
            for obj in memes_list:
                if (obj.date > group.last_meme_date) & (len(obj.text) <= 280):
                    log("Отправка мема из группы \"{}\".".format(group.name))
                    obj.send(user.chat_id)
                    group.last_meme_date = obj.date


def update_bot():
    log("Обновление бота.")
    global bot
    for obj in bot.get_updates():
        if obj.text is None:
            continue
        log("Получено сообщение: {}".format(obj.text))
        if obj.text[0] == '/':
            bot_commands(obj)


def command_error(chat_id):
    bot.send_message(chat_id=chat_id, text="Неизвестная команда. Введите /help для помощи.")


def bot_commands(message):
    global bot
    global users_list
    text = message.text
    chat_id = message.chat_id
    command = text[1:].split()[0]
    attributes_num = len(text.split())-1
    user = User(chat_id)
    for obj in users_list:
        if obj.chat_id == chat_id:
            user = obj
            break

    if command == 'start':
        if attributes_num == 0:
            if user not in users_list:
                log("Создание нового пользователя.")
                users_list.append(user)
        else:
            command_error(chat_id)

    if command == "add":
        if attributes_num == 1:
            attribute = text.split()[1]
            try:
                group = Group(attribute)
            except AttributeError:
                bot.send_message(chat_id=chat_id, text="Группа \"{}\" не найдена.".format(attribute))
                return

            if group in user.groups_list:
                bot.send_message(chat_id=chat_id, text="Группа \"{}\" уже добавлена.".format(group.name))
                return

            log("Добавление группы: {}".format(group.name))
            user.groups_list.append(group)
            bot.send_message(chat_id=chat_id, text="Группа \"{}\" добавлена.".format(group.name))
            user.groups_list.sort()
        else:
            command_error(chat_id)

    if command == 'help':
        if attributes_num == 0:
            bot.send_message(chat_id=chat_id, text=("/add <group_id> Добавление группы. group_id - id сообщества\n"
                                                    "/remove <num> Удаление группы. num - номер в списке\n"
                                                    "/list Список групп\n"
                                                    "/help Список команд"))
        else:
            command_error(chat_id)

    if command == 'list':
        if attributes_num == 0:
            ans = ""
            for i in range(len(user.groups_list)):
                ans += "{}. {}\n".format(i + 1, user.groups_list[i].name)
            if ans == "":
                ans = "Пока не добавлено ни одной группы."
            bot.send_message(chat_id=chat_id, text=ans)
        else:
            command_error(chat_id)

    if command == 'remove':
        if attributes_num == 1:
            try:
                attribute = int(text.split()[1])
            except ValueError:
                bot.send_message(chat_id=chat_id, text="<num> должно быть числом.")
                return
            if len(user.groups_list) == 0:
                bot.send_message("Список групп пуст.")
                return
            if attribute > len(user.groups_list):
                bot.send_message(chat_id=chat_id, text="Слишком большое число")
                return
            log("Удаление группы: {}.".format(user.groups_list[attribute - 1].name))
            bot.send_message(chat_id=chat_id,
                             text="Группа \"" + user.groups_list.pop(attribute - 1).name + "\" удалена.")
        else:
            command_error(chat_id)


class User:
    def __init__(self, chat_id):
        self.chat_id = chat_id
        self.groups_list = []

    def __str__(self):
        groups_list_str = ["{}\n".format(c) for c in self.groups_list]
        res = "{}\n{}\n".format(self.chat_id, len(self.groups_list))
        for obj in self.groups_list:
            res += "{}".format(obj)
        return res


def read_user(fin):
    res = User(int(fin.readline()))
    groups_num = int(fin.readline())
    for _ in range(groups_num):
        res.groups_list.append(read_group(fin))
    return res


if __name__ == '__main__':
    users_list = []
    with open("data.txt", "r") as fin:
        lastUpdateID = int(fin.readline())
        user_num = int(fin.readline())
        for _ in range(user_num):
            users_list.append(read_user(fin))
    try:
        bot = Telebot(TOKEN, lastUpdateID, TIMEOUT)
        while True:
            update_groups()
            update_bot()
    finally:
        lastUpdateID = bot.offset-1
        with open("data.txt", "w") as fout:
            fout.write("{}\n".format(lastUpdateID))
            fout.write("{}\n".format(len(users_list)))
            for obj in users_list:
                fout.write(str(obj))
