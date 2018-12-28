from mycroft import MycroftSkill, intent_file_handler, intent_handler, util, audio
from mycroft.skills.audioservice import AudioService
from mycroft.util.parse import extract_datetime, extract_number, normalize
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

    @intent_file_handler('remind.intent')
    def handle_reminder(self, msg=None):
        tnow = datetime.datetime.now().replace(hour=0,minute=0,second=0,microsecond=0)
        tstring = normalize(msg.data['time'])
        reminder = msg.data['reminder']

        ret = extract_datetime(tstring,tnow)
        if not ret:
            self.speak("I couldn't understand when you needed to be reminded.")
            return
        t = ret[0]

        #Verify data
        td = t-tnow
        deltadays = td.days + (td.seconds + td.microseconds/1E6)/86400;
        if deltadays<0:
            self.speak("I can't do that, the reminder is in the past.")
            return

        timestring = "when you wake up"
        datestring = ""
        if t.hour==0 and t.minute==0 and t.second==0 and t.microsecond==0: #Day Reminder
            t = t.replace(hour=6, minute=0)
        else:
            timestring = "at " + util.format.nice_time(t,'en-us',use_24hour=True)

        if deltadays<1:
            datestring = "today"
        elif deltadays<2:
            datestring = "tomorrow"
        elif deltadays<3:
            datestring = "day after tomorrow"
        elif deltadays<=7:
            datestring = "on " + t.strftime("%A")
        elif t.year != tnow.year:
            datestring = "on " + t.strftime("%A, %B %d, %Y")
        elif t.month != tnow.month:
            datestring = "on " + t.strftime("%A, %B %d")
        else :
            datestring = "on " + t.strftime("%A the %d")

        self.speak("The time string is " + tstring)
        audio.wait_while_speaking()
        self.speak("Okay. I will remind you " + datestring + " " + timestring + " to " + reminder + ".")

        #self.speak_dialog('pradu')
        #self.speak(message.data['reminder'])

    def update(self):
        tnow = datetime.datetime.now()
        if tnow.hour==5 and tnow.minute==54:
            self.audio_service.play("/opt/mycroft/skills/pradu-skill/audio/Eminem_Lose_Yourself.mp3")
        if tnow.hour>=6 and ( tnow.hour<22 or (tnow.hour==22 and tnow.minute==0) ) and ( tnow.minute==0 or tnow.minute==15 or tnow.minute==30 or tnow.minute==45 ):
            audio.wait_while_speaking()
            self.speak("It's " + util.format.nice_time(tnow) + ".",use_24hour=True)

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

