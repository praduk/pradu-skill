from mycroft import MycroftSkill, intent_file_handler, intent_handler, util, audio
from mycroft.skills.audioservice import AudioService
import datetime
import os

class TodoItem:
    def __init__(self):
        self.time = datetime.datetime(1,1,1)
        self.desc = ""

class Todo(list):
    def parse(self):
        fn = os.environ['HOME'] + '/today.txt'
        datetoday = datetime.datetime.today()
        with open(fn,"r") as f:
            data = f.read().splitlines()
            for x in data:
                if len(x)<1 or x[0]=='#' or x[0]=='\n':
                    continue
                i = TodoItem()
                y = x.split(" ", 1)
                time = int(y[0])
                i.time = datetime.datetime(datetoday.year, datetoday.month, datetoday.day, time//100, time%100)
                i.desc = y[1]
                self.append(i)

class Pradu(MycroftSkill):
    def __init__(self):
        MycroftSkill.__init__(self)

    def get_intro_message(self):
        return "Pradu's Custom Skills Loaded"

    def initialize(self):
        self.audio_service = AudioService(self.emitter)
        tnext = datetime.datetime.now().replace(second=0,microsecond=0) + datetime.timedelta(seconds=60)
        self.schedule_repeating_event(self.update,tnext,60,None,None)
        self.make_active()

    @intent_file_handler('reminder.intent')
    def handle_reminder(self, message):
        #self.speak_dialog('pradu')
        self.speak(message.data['reminder'])

    def update(self):
        tnow = datetime.datetime.now()
        if tnow.hour==5 and tnow.minute==54:
            self.audio_service.play("/opt/mycroft/skills/pradu-skill/audio/Eminem_Lose_Yourself.mp3")
        if tnow.hour>=6 and ( tnow.hour<22 or (tnow.hour==22 and tnow.minute==0) ) and ( tnow.minute==0 or tnow.minute==15 or tnow.minute==30 or tnow.minute==45 ):
            audio.wait_while_speaking()
            self.speak("It's " + util.format.nice_time(tnow) + ".")

        todaysList = Todo()
        todaysList.parse()
        for task in todaysList:
            if (tnow - datetime.timedelta(seconds=30)) <= task.time and task.time <= (tnow + datetime.timedelta(seconds=30)):
                audio.wait_while_speaking()
                p = util.play_wav("/opt/mycroft/skills/pradu-skill/audio/notification.wav")
                p.wait()
                self.speak(task.desc)

def create_skill():
    return Pradu()

