from mycroft import MycroftSkill, intent_file_handler, intent_handler, util, audio
from mycroft.skills.audioservice import AudioService
from mycroft.util.parse import extract_datetime, extract_number, normalize
import time
import datetime
import os
import re
import pickle
from threading import Lock

#prefix = os.environ['HOME'] + '/planning/'
prefix = '/data/mycroft/'

def pullServer():
    os.system("/usr/bin/rsync -avg --omit-dir-times --delete -e ssh data@pradu.us:/data/mycroft/ /data/mycroft/")
def pushServer():
    os.system("/usr/bin/rsync -avg --omit-dir-times --delete -e ssh /data/mycroft/ data@pradu.us:/data/mycroft/")


class TodoItem:
    def __init__(self):
        self.time = datetime.datetime(1,1,1)
        self.desc = ""
    def isCommand(self):
        return len(self.desc)>0 and self.desc[0]=='!'
    def getCommand(self):
        return self.desc[1:]

class Todo(list):
    def parse(self,fnstem):
        fn = prefix + fnstem + '.txt'
        datetoday = datetime.datetime.today()
        try:
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
        except:
            pass


def valid_time(input_string):
    td = extract_datetime(input_string,datetime.datetime.now())
    return td

def timedeltaToString(td):
    if td<datetime.timedelta(0):
        td = -td
    days = td.days
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    retstr = ""
    if days!=0:
        retstr = str(days) + " days, "
    if hours!=0:
        retstr = retstr + str(hours) + " hours, "
    retstr = retstr + str(minutes) + " minutes"
    return retstr

class Pradu(MycroftSkill):
    def __init__(self):
        MycroftSkill.__init__(self)

    def get_intro_message(self):
        return "Pradu's Custom Skills Loaded"

    def _schedule(self):
        self.scheduleLock.acquire()
        tnext = datetime.datetime.now().replace(second=0,microsecond=0) + datetime.timedelta(seconds=60)
        if (tnext-self.tlast).seconds > 30:
            self.cancel_scheduled_event("Update")
            self.schedule_event(self.update,tnext,name="Update")
            self.log.info("Scheduling Next Update: " + self._unique_name("Update") + " "  + tnext.strftime("%A, %B %d, %Y,  %H:%M") + " (last was " + self.tlast.strftime("%A, %B %d, %Y,  %H:%M") + ")")
            self.tlast = tnext
        self.scheduleLock.release()

    def initialize(self):
        self.audio_service = AudioService(self.bus)
        self.tlast = datetime.datetime.now() + datetime.timedelta(seconds=-60)
        self.scheduleLock = Lock()
        self._schedule()
        #self.schedule_repeating_event(self.update,tnext,60,None,None)
        #self.make_active()


    @intent_file_handler('goal.intent')
    def handle_goal(self, msg=None):
        if not ('goal' in msg.data):
            return
        fn = prefix + 'goals.txt'
        with open(fn,"a+") as f:
            f.write(msg.data['goal'] + '\n')
            self.speak('Added')

    @intent_file_handler('query.intent')
    def handle_query(self,msg=None):
        tnow = datetime.datetime.now().replace(second=0,microsecond=0)
        todaysList = self.getAllList(tnow)
        prevTime = None
        prevTask = None
        nextTime = None
        nextTask = None
        for x in todaysList:
            if (x.time <= tnow) and ( (not prevTime) or x.time >= prevTime ):
                prevTime = x.time
                prevTask = x.desc
            if (x.time > tnow) and ( (not nextTime) or x.time <= nextTime ):
                nextTime = x.time
                nextTask = x.desc
        if prevTask:
            self.speak("Now for " + timedeltaToString(tnow-prevTime) + ". " + prevTask)
        if nextTask:
            self.speak("Next in " + timedeltaToString(nextTime-tnow) + ". " + nextTask)

    @intent_file_handler('remind.intent')
    def handle_reminder(self, msg=None):
        tnow = datetime.datetime.now().replace(hour=0,minute=0,second=0,microsecond=0)
        tstring = ""
        if not ('time' in msg.data):
            audio.wait_while_speaking()
            tstring = self.get_response("When did you want to be reminded?",num_retries=3, validator=valid_time)
            if not tstring:
                audio.wait_while_speaking()
                self.speak("Okay I'm giving up.")
                return
        else:
            tstring = msg.data['time']

        reminder = ""
        if not ('reminder' in msg.data):
            audio.wait_while_speaking()
            reminder = self.get_response("What did you want to be reminded of?",num_retries=3)
            if not reminder:
                audio.wait_while_speaking()
                self.speak("Okay I'm giving up.")
                return
        else:
            reminder = msg.data['reminder']
        rep=[("yourself",["myself"]), ("you",["I", "me"]), ("your", ["my"])]
        d={ k : "\\b(?:" + "|".join(v) + ")\\b" for k,v in rep}
        for k,r in d.items(): reminder=re.sub(r,k,reminder)
        ret = extract_datetime(tstring,datetime.datetime.now())
        if not ret:
            self.speak("I couldn't understand when you needed to be reminded. Try again.")
            return
        t = ret[0]

        #Verify data
        td = t-tnow
        deltadays = td.days + (td.seconds + td.microseconds/1E6)/86400;
        if deltadays<0:
            audio.wait_while_speaking()
            self.speak("I can't do that, the reminder is in the past.")
            return

        timestring = "when you wake up"
        datestring = ""
        if t.hour==0 and t.minute==0 and t.second==0 and t.microsecond==0: #Day Reminder
            t = t.replace(hour=5, minute=55)
        else:
            timestring = "at " + util.format.nice_time(t,'en-us',use_24hour=True)

        datestring = util.format.nice_date(t,lang='en-us',now=datetime.datetime.now())
        if deltadays<1:
            datestring = "today"
        elif deltadays<2:
            datestring = "tomorrow"
        elif deltadays<3:
            datestring = "day after tomorrow"
        elif deltadays<=7:
            datestring = "on " + t.strftime("%A")

        audio.wait_while_speaking()
        if self.ask_yesno("You would like to be reminded " + datestring + " " + timestring + " to " + reminder + ".  Is that correct?")!="yes":
            self.speak("Okay. Please repeat your request if you would like a reminder.")
            return

        fn = prefix + "reminders.pkl"
        try:
            with open(fn,"rb") as f:
                remDict = pickle.load(f)
        except:
            remDict = dict()

        self.speak("Okay. I will remind you " + datestring + " " + timestring + " to " + reminder + ".")
        self.log.info("Adding reminder: [" + t.strftime("%A, %B %d, %Y,  %H:%M") + "]  " + reminder + ".")

        if t in remDict:
            remDict[t] = remDict[t] + ".  " + reminder
        else:
            remDict[t] = reminder

        with open(fn,"wb") as f:
            pickle.dump(remDict,f)
            pushServer()

        #self.speak_dialog('pradu')
        #self.speak(message.data['reminder'])

    def getTodoList(self,t):
        todaysList = Todo()
        todaysList.parse("everyday")
        todaysList.parse(t.strftime("weekly/%A"))
        todaysList.parse(t.strftime("date/%m%d"))
        return todaysList

    def getAllList(self,t):
        todaysList = self.getTodoList(t)
        # Add Reminders to Today's List
        fn = prefix + "reminders.pkl"
        remDict = dict()
        try:
            with open(fn,"rb") as f:
                remDict = pickle.load(f)
        except:
            pass
        for t in remDict:
            x=TodoItem()
            x.time = t
            x.desc = "Reminder. " + remDict[t]
            todaysList.append(x)
        todaysList.sort(key=lambda TodoItem: TodoItem.time)
        return todaysList

    def dailyOverview(self):
        tnow = datetime.datetime.now()
        todaysList = self.getAllList(tnow)

        p = util.play_wav("/opt/mycroft/skills/pradu-skill/audio/fanfare.wav")
        p.wait()
        for x in todaysList:
            timeString = util.format.nice_time(x.time,'en-us',use_24hour=True)
            self.speak("At " + timeString + ". " + x.desc)
            time.sleep(0.25)
            audio.wait_while_speaking()
            q = util.play_wav("/opt/mycroft/skills/pradu-skill/audio/click.wav")
            q.wait()

    def update(self):
        self._schedule()
        tnow = datetime.datetime.now()
        if tnow.hour==5 and tnow.minute==46:
            self.log.info("Playing Wake-Up Song")
        #    self.audio_service.play("/data/music/Eminem_Lose_Yourself.mp3")
        #    self.audio_service.play("/data/music/JessGlynne_CleanBandit.mp3")
            self.audio_service.play("/data/music/Deadmau5_The_Veldt.mp3")
        if tnow.hour>=6 and ( tnow.hour<22 or (tnow.hour==22 and tnow.minute==0) ) and ( tnow.minute==0 or tnow.minute==15 or tnow.minute==30 or tnow.minute==45 ):
            self.log.info("Notification of Current Time")
            audio.wait_while_speaking()
            self.speak("It's " + util.format.nice_time(tnow,use_24hour=True) + ".")
            pullServer()
            audio.wait_while_speaking()

        todaysList = self.getTodoList(tnow)

        firstNotification = True
        if len(todaysList) > 0:
            for task in todaysList:
                if (tnow - datetime.timedelta(seconds=30)) <= task.time and task.time <= (tnow + datetime.timedelta(seconds=30)):
                    if task.isCommand():
                        os.system(task.getCommand())
                    else:
                        if firstNotification:
                            self.log.info("Playing Notifications")
                            firstNotification = False
                            p = util.play_wav("/opt/mycroft/skills/pradu-skill/audio/notification.wav")
                            p.wait()
                        else:
                            q = util.play_wav("/opt/mycroft/skills/pradu-skill/audio/click.wav")
                            q.wait()
                        self.log.info("Notification: " + task.desc)
                        self.speak(task.desc)
                        audio.wait_while_speaking()

        # One Off Reminders
        fn = prefix + "reminders.pkl"
        try:
            with open(fn,"rb") as f:
                remDict = pickle.load(f)
        except:
            remDict = dict()
        for t in list(remDict):
            if t <= tnow + datetime.timedelta(seconds=30):
                reminder = remDict.pop(t)
                if firstNotification:
                    firstNotification = False
                    p = util.play_wav("/opt/mycroft/skills/pradu-skill/audio/notification.wav")
                    p.wait()
                else:
                    q = util.play_wav("/opt/mycroft/skills/pradu-skill/audio/click.wav")
                    q.wait()
                self.log.info("Reminder: " + reminder)
                self.speak(reminder)
                audio.wait_while_speaking()
        with open(fn,"wb") as f:
            pickle.dump(remDict,f)
            pushServer()

        # Daily Overview
        if tnow.hour==5 and tnow.minute==55:
            self.dailyOverview()


def create_skill():
    return Pradu()

