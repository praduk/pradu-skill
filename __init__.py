from mycroft import MycroftSkill, intent_file_handler, intent_handler, util, audio
from mycroft.skills.audioservice import AudioService
from mycroft.util.parse import extract_datetime, extract_number, normalize
import time
import datetime
import os
import re
import pickle
import socket
import sys
import _thread as thread
import time
from threading import Lock

#prefix = os.environ['HOME'] + '/planning/'
prefix = '/data/mycroft/'
skilldir= '/opt/mycroft/skills/pradu-skill.praduk/'

piUnits=["pi0", "pi1", "pi2", "praduSpectre", "blueideal"]
def dumpToPi(pi,x):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.sendto(x,(socket.gethostbyname(pi+".local"),54321))
    except:
        pass
def broadcast(data):
    x = pickle.dumps(data)
    for pi in piUnits:
        thread.start_new_thread(dumpToPi,(pi,x))
def selfcast(data):
    x = pickle.dumps(data)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.sendto(x,("",54321))
    except:
        pass

class TodoItem:
    def __init__(self):
        self.time = datetime.datetime(1,1,1)
        self.desc = ""
    def isLocalCommand(self):
        if len(self.desc)<=0 or self.desc[0]!='@':
            return False
        else:
            (uname, rest) = self.desc.split(" ",1)
            return uname[1:]==socket.gethostname()
    def isCommand(self):
        return len(self.desc)>0 and (self.desc[0]=='!' or self.isLocalCommand())
    def isActivity(self):
        return len(self.desc)>0 and not (self.desc[0]=='!' or self.desc[0]=='@')
    def isImportant(self):
        return len(self.desc)>0 and self.desc[0]=='*'
    def makeImportant(self):
        if self.isActivity():
            self.desc = '*' + self.desc
    def getText(self):
        if self.isLocalCommand():
            (uname, cmd) = self.desc.split(" ",1)
            return cmd
        elif self.isCommand() or self.isImportant():
            return self.desc[1:]
        else:
            return self.desc


class Todo(list):
    def parse(self,t,fnstem,offset=0):
        fn = prefix + t.strftime(fnstem) + '.txt'
        try:
            with open(fn,"r") as f:
                data = f.read().splitlines()
                for x in data:
                    if len(x)<1 or x[0]=='#' or x[0]=='\n':
                        continue
                    i = TodoItem()
                    y = x.split(" ", 1)
                    if y[0]=='include':
                        self.parse(t,"templates/"+y[1])
                    elif y[0]=='template':
                        z = y[1].split(" ", 1)
                        num = int(z[0])
                        switchSign = False
                        if num<0:
                            switchSign = True
                            num = -num
                        tbase = 60*(num//100) + num%100
                        if switchSign:
                            tbase = -tbase
                        self.parse(t,"templates/"+z[1],tbase)
                    else:
                        time = int(y[0])
                        i.time = datetime.datetime(t.year, t.month, t.day, time//100, time%100) + datetime.timedelta(minutes=offset)
                        i.desc = y[1]
                        self.append(i)
            return True
        except Exception as e:
            return False


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
        self.scheduleLock = Lock()

    def pullServer(self):
        if not socket.gethostname()=='pi0':
            #serverinfo = 'data@pradu.us'
            serverinfo = 'pradu@pi0.local'
            self.log.info("==Server Pull==")
            os.system("/usr/bin/rsync -avg --omit-dir-times --delete -e ssh " + serverinfo + ":/data/mycroft/ " + prefix)
            self.log.info("^^Server Pull^^")
    def pushServer(self):
        if not socket.gethostname()=='pi0':
            #serverinfo = 'data@pradu.us'
            serverinfo = 'pradu@pi0.local'
            self.log.info("==Server Push==")
            os.system("/usr/bin/rsync -avg --omit-dir-times --delete -e ssh " + prefix + " " + serverinfo + ":/data/mycroft/")
            self.log.info("^^Server Push^^")

    def get_intro_message(self):
        return "Pradu's Custom Skills Loaded"

    def _schedule(self):
        didntschedule = True
        self.scheduleLock.acquire()
        tnext = datetime.datetime.now().replace(second=0,microsecond=0) + datetime.timedelta(seconds=60)
        if (tnext-self.tlast).seconds > 30:
            #self.cancel_scheduled_event("Update")
            self.schedule_event(self.update,tnext,name="Update")
            self.log.info("Next Update: " + self._unique_name("Update") + " "  + tnext.strftime("%A, %B %d, %Y,  %H:%M") + " (last was " + self.tlast.strftime("%A, %B %d, %Y,  %H:%M") + ")")
            self.tlast = tnext
            didntschedule = False
        self.scheduleLock.release()
        return didntschedule

    def initialize(self):
        self.audio_service = AudioService(self.bus)
        self.tlast = datetime.datetime.now() + datetime.timedelta(seconds=-60)
        self.make_active()
        self.update()
        #self._schedule()
        #self.schedule_repeating_event(self.update,tnext,60,None,None)


    @intent_file_handler('goal.intent')
    def handle_goal(self, msg=None):
        if not ('goal' in msg.data):
            return
        fn = prefix + 'goals.txt'
        self.pullServer()
        with open(fn,"a+") as f:
            f.write(msg.data['goal'] + '\n')
            self.speak('Added')
            self.pushServer()

    @intent_file_handler('timer.intent')
    def set_timer(self, msg=None):
        seconds = 0
        minutes = 0
        hours   = 0
        if 'minute' in msg.data:
            minutes = extract_number(msg.data['minute'])
        if 'second' in msg.data:
            seconds = extract_number(msg.data['second'])
        if 'hour' in msg.data:
            hours = extract_number(msg.data['hour'])
        if minutes>0 or seconds>0 or hours>0:
            ttimer = datetime.datetime.now() + datetime.timedelta(hours=hours,minutes=minutes,seconds=seconds)
            broadcast(('timer', ttimer))
            self.speak("Timer Set")
    @intent_file_handler('canceltimer.intent')
    def cancel_timer(self, msg=None):
        broadcast(('stoptimer',))
    @intent_file_handler('light.intent')
    def toggle_light(self, msg=None):
        if 'number' in msg.data:
            if msg.data['number']=='bedroom':
                selfcast(('toggle',['Light0']))
            if msg.data['number']=='living room':
                selfcast(('toggle',['Light1']))
            if msg.data['number']=='bathroom':
                selfcast(('toggle',['Light2','Light3','Light4']))
            if msg.data['number']=='game room' or msg.data['number']=='workout room' or msg.data['number']=='gym' or msg.data['number']=='gym room':
                selfcast(('toggle',['Light5']))
            if msg.data['number']=='outside':
                selfcast(('toggle',['Outside0']))
            else:
                selfcast(('toggle',['Light'+str(extract_number(msg.data['number']))]))
        else:
            self.speak("I don't know what light to toggle")


    def updateGui(self):
        tnow = datetime.datetime.now().replace(second=0,microsecond=0)
        todaysList = self.getAllList(tnow)
        prevTime = None
        prevTask = None
        nextTime = None
        nextTask = None
        for x in todaysList:
            if x.isActivity():
                if (x.time <= tnow) and ( (not prevTime) or x.time >= prevTime ):
                    prevTime = x.time
                    prevTask = x.getText()
                if (x.time > tnow) and ( (not nextTime) or x.time <= nextTime ):
                    nextTime = x.time
                    nextTask = x.getText()
        if prevTask:
            selfcast(("activity",prevTime,prevTask))
        if nextTask:
            selfcast(("activity",nextTime,nextTask))
        

    @intent_file_handler('query.intent')
    def handle_query(self,msg=None):
        tnow = datetime.datetime.now().replace(second=0,microsecond=0)
        todaysList = self.getAllList(tnow)
        prevTime = None
        prevTask = None
        nextTime = None
        nextTask = None
        for x in todaysList:
            if not x.isActivity():
                if (x.time <= tnow) and ( (not prevTime) or x.time >= prevTime ):
                    prevTime = x.time
                    prevTask = x.getText()
                if (x.time > tnow) and ( (not nextTime) or x.time <= nextTime ):
                    nextTime = x.time
                    nextTask = x.getText()
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
        remDict = dict()
        try:
            with open(fn,"rb") as f:
                remDict = pickle.load(f)
        except:
            pass

        self.speak("Okay. I will remind you " + datestring + " " + timestring + " to " + reminder + ".")
        self.log.info("Adding reminder: [" + t.strftime("%A, %B %d, %Y,  %H:%M") + "]  " + reminder + ".")
        self.pullServer()

        if t in remDict:
            remDict[t] = remDict[t] + ".  " + reminder
        else:
            remDict[t] = reminder

        with open(fn,"wb") as f:
            pickle.dump(remDict,f)
            self.log.info("Pickle dump")
        self.pushServer()

        #self.speak_dialog('pradu')
        #self.speak(message.data['reminder'])

    def getTodoList(self,t):
        todaysList = Todo()
        # Prase File According to Priority
        if todaysList.parse(t,"date/%Y%m%d"): pass
        elif todaysList.parse(t,"yearly/%m%d"): pass
        elif todaysList.parse(t,"monthly/%d"): pass
        elif todaysList.parse(t,"weekly/%A"): pass
        else: todaysList.parse(t,"everyday")
        todaysList.sort(key=lambda TodoItem: TodoItem.time)
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
            x.desc = "*Reminder. " + remDict[t]
            todaysList.append(x)
        todaysList.sort(key=lambda TodoItem: TodoItem.time)
        return todaysList

    def dailyOverview(self):
        tnow = datetime.datetime.now()
        todaysList = self.getAllList(tnow)

        util.play_wav(skilldir + "audio/fanfare.wav").wait()
        for x in todaysList:
            if x.isImportant():
                timeString = util.format.nice_time(x.time,'en-us',use_24hour=True)
                self.speak("At " + timeString + ". " + x.getText())
                time.sleep(0.25)
                audio.wait_while_speaking()
                util.play_wav(skilldir+"audio/fingersnap.wav").wait()

    def update(self):
        if self._schedule():
            return
        tnow = datetime.datetime.now()
        playedSomething = False
        #if tnow.hour==5 and tnow.minute==46:
        #    self.log.info("Playing Wake-Up Song")
        ##    self.audio_service.play("/data/music/Eminem_Lose_Yourself.mp3")
        ##    self.audio_service.play("/data/music/JessGlynne_CleanBandit.mp3")
        #    self.audio_service.play("/data/music/Deadmau5_The_Veldt.mp3")
        #    playedSomething=True
        if tnow.hour>=6 and ( tnow.hour<22 or (tnow.hour==22 and tnow.minute==0) ) and ( tnow.minute==0 or tnow.minute==15 or tnow.minute==30 or tnow.minute==45 ):
            self.log.info("Notification of Current Time")
            audio.wait_while_speaking()
            util.play_wav(skilldir + "audio/fingersnap.wav").wait()
            self.speak("It's " + util.format.nice_time(tnow,use_24hour=True) + ".")
            self.pullServer()
            audio.wait_while_speaking()
            playedSomething=True

        todaysList = self.getTodoList(tnow)

        firstNotification = True
        if len(todaysList) > 0:
            for task in todaysList:
                if (tnow - datetime.timedelta(seconds=30)) <= task.time and task.time <= (tnow + datetime.timedelta(seconds=30)):
                    if task.isCommand():
                        self.log.info("Command: " + task.getText())
                        os.system(task.getText())
                    elif task.isActivity():
                        if firstNotification:
                            self.log.info("Playing Notifications")
                            firstNotification = False
                            util.play_wav(skilldir + "audio/notification.wav").wait()
                        else:
                            q = util.play_wav(skilldir + "audio/fingersnap.wav").wait()
                        self.log.info("Notification: " + task.getText())
                        self.speak(task.getText())
                        audio.wait_while_speaking()
                        playedSomething = True

        # One Off Reminders
        fn = prefix + "reminders.pkl"
        remDict = dict()
        try:
            with open(fn,"rb") as f:
                remDict = pickle.load(f)
        except:
            pass
        remDict_haschanged = False
        for t in list(remDict):
            if t <= tnow + datetime.timedelta(seconds=30):
                reminder = remDict.pop(t)
                remDict_haschanged = True
                if firstNotification:
                    firstNotification = False
                    util.play_wav(skilldir + "audio/notification.wav").wait()
                else:
                    util.play_wav(skilldir + "audio/fingersnap.wav").wait()
                self.log.info("Reminder: " + reminder)
                self.speak(reminder)
                audio.wait_while_speaking()
                playedSomething = True
        if remDict_haschanged:
            self.pullServer()
            with open(fn,"wb") as f:
                pickle.dump(remDict,f)
                self.log.info("Pickle dump")
                self.pushServer()

        # Daily Overview
        if tnow.hour==5 and tnow.minute==55:
            self.dailyOverview()
            playedSomething = True

        # To Keep BlueTooth Speaker Alive
        #util.play_wav(skilldir + "audio/softknock.wav").wait()

        # Update GUI
        self.updateGui()


def create_skill():
    return Pradu()

