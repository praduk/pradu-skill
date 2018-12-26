from mycroft import MycroftSkill, intent_file_handler


class Pradu(MycroftSkill):
    def __init__(self):
        MycroftSkill.__init__(self)

    @intent_file_handler('pradu.intent')
    def handle_pradu(self, message):
        self.speak_dialog('pradu')


def create_skill():
    return Pradu()

