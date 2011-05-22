#
# PowerAdmin Plugin for BigBrotherBot(B3) (www.bigbrotherbot.com)
# Copyright (C) 2008 Mark Weirath (xlr8or@xlr8or.com)
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
#
# CHANGELOG :
# 2011-05-22 - 0.2 -Courgette
# * add call vote protector for teaching noobs not to call kick/ban agains admins
#
__version__ = '0.2'
__author__  = 'xlr8or, Courgette'

import b3
import b3.events
import b3.plugin

#--------------------------------------------------------------------------------------------------
class PoweradminhfPlugin(b3.plugin.Plugin):

    _adminPlugin = None
    _enableTeamBalancer = None
    
    _matchmode = False
    _match_plugin_disable = []
    _matchManager = None
    
    _ignoreBalancingTill = 0
    
    _currentVote = None
    _auto_unban_level = None
    
    def startup(self):
        """\
        Initialize plugin settings
        """

        # get the admin plugin so we can register commands
        self._adminPlugin = self.console.getPlugin('admin')
        if not self._adminPlugin:
            # something is wrong, can't start without admin plugin
            self.error('Could not find admin plugin')
            return False

        # register our commands
        if 'commands' in self.config.sections():
            for cmd in self.config.options('commands'):
                level = self.config.get('commands', cmd)
                sp = cmd.split('-')
                alias = None
                if len(sp) == 2:
                    cmd, alias = sp

                func = self.getCmd(cmd)
                if func:
                    self._adminPlugin.registerCommand(self, cmd, level, func, alias)

        # do not balance on the 1st minute after bot start
        self._ignoreBalancingTill = self.console.time() + 60

        # Register our events
        self.verbose('Registering events')
        self.registerEvent(b3.events.EVT_CLIENT_TEAM_CHANGE)
        self.registerEvent(b3.events.EVT_GAME_ROUND_START)
        self.registerEvent(b3.events.EVT_CLIENT_AUTH)
        self.registerEvent(b3.events.EVT_CLIENT_VOTE_START)
        self.registerEvent(b3.events.EVT_SERVER_VOTE_END)
        self.debug('Started')


    def getCmd(self, cmd):
        cmd = 'cmd_%s' % cmd
        if hasattr(self, cmd):
            func = getattr(self, cmd)
            return func
    
        return None


    def onLoadConfig(self):
        self.LoadTeamBalancer()
        self.LoadMatchMode()
        self.LoadVoteProtector()

    def LoadTeamBalancer(self):
        # TEAMBALANCER SETUP
        try:
            self._enableTeamBalancer = self.config.getboolean('teambalancer', 'enabled')
        except:
            self._enableTeamBalancer = False
            self.debug('Using default value (%s) for Teambalancer enabled', self._enableTeamBalancer)
      
    def LoadMatchMode(self):
        # MATCH MODE SETUP
        self._match_plugin_disable = []
        try:
            self.debug('pamatch_plugins_disable/plugin : %s' %self.config.get('pamatch_plugins_disable/plugin'))
            for e in self.config.get('pamatch_plugins_disable/plugin'):
                self.debug('pamatch_plugins_disable/plugin : %s' %e.text)
                self._match_plugin_disable.append(e.text)
        except:
            self.debug('Can\'t setup pamatch disable plugins because there is no plugins set in config')
      
    def LoadVoteProtector(self):
        try:
            self._auto_unban_level = self.config.getint('voteprotector','auto_unban_level')
        except Exception, err:
            self._auto_unban_level = 20
            self.warning('can\'t read auto_unban_level from config. Using default (%s)' % err)
        self.debug('voteprotector/auto_unban_level : %s' % self._auto_unban_level)


##################################################################################################

    def onEvent(self, event):
        """\
        Handle intercepted events
        """
        if event.type == b3.events.EVT_CLIENT_TEAM_CHANGE:
            self.onTeamChange(event.data, event.client)
        elif event.type == b3.events.EVT_GAME_ROUND_START:
            # do not balance on the 1st minute after bot start
            self._ignoreBalancingTill = self.console.time() + 60
        elif event.type == b3.events.EVT_CLIENT_AUTH:
            self.onClientAuth(event.data, event.client)
        elif event.type == b3.events.EVT_CLIENT_VOTE_START:
            self.onVoteStart(event)
        elif event.type == b3.events.EVT_SERVER_VOTE_END:
            self.onVoteEnd(event)


    def cmd_paautobalance(self, data, client=None, cmd=None):
        """\
        <on/off> Switch Homefronts autobalancer on or off
        """
        if data:
            if data.lower() in ('on', 'off'):
                if data.lower() == 'on':
                    _astate = 'true'
                else:
                    _astate = 'false'
                self.console.write('admin SetAutoBalance %s' % _astate)
        if not data:
            client.message('missing parameter, try !help paautobalance')
            return False


    def cmd_pateams(self ,data , client, cmd=None):
        """\
        Make the teams balanced
        """
        if client:
            team1players, team2players = self.getTeams()
            
            # if teams are uneven by one or even, then stop here
            gap = abs(len(team1players) - len(team2players))
            if gap <= 1:
                client.message('Teams are balanced, T1: %s, T2: %s (diff: %s)' %(len(team1players), len(team2players), gap))
            else:
                self.teambalance()


    def cmd_pateambalance(self, data, client=None, cmd=None):
        """\
        <on/off> - Set teambalancer on/off
        Setting teambalancer on will warn players that make teams unbalanced
        """
        if not data:
            if client:
                if self._enableTeamBalancer:
                    client.message("team balancing is on")
                else:
                    client.message("team balancing is off")
            else:
                self.debug('No data sent to cmd_teambalance')
        else:
            if data.lower() in ('on', 'off'):
                if data.lower() == 'off':
                    self._enableTeamBalancer = False
                    client.message('Teambancer is now disabled')
                elif data.lower() == 'on':
                    self._enableTeamBalancer = True
                    client.message('Teambancer is now enabled')
            else:
                if client:
                    client.message("Invalid data, expecting 'on' or 'off'")
                else:
                    self.debug('Invalid data sent to cmd_teambalance : %s' % data)
    

    def cmd_panextmap(self, data, client=None, cmd=None):
        """\
        Force server to the Next Map in rotation
        """
        self.console.write('admin NextMap')


    def cmd_payell(self, data, client, cmd=None):
        """\
        <msg>- Yell message to all players
        """
        if client :
            if not data:
                client.message('missing parameter, try !help payell')
                return False
            self.console.saybig('%s: %s' % (client.name, data))

        
    def cmd_paversion(self, data, client, cmd=None):
        """\
        This command identifies PowerAdminHF version and creator.
        """
        #client.message(message)
        cmd.sayLoudOrPM(client, 'I am PowerAdminHF version %s by %s' % (__version__, __author__))
        return None
        

    def cmd_paident(self, data, client, cmd=None):
        """\
        [<name>] - show the ip and guid of a player
        (You can safely use the command without the 'pa' at the beginning)
        """
        input = self._adminPlugin.parseUserCmd(data)
        if not input:
            # assume the player wants his own ident
            try:
                cmd.sayLoudOrPM(client, '%s: %s' % (client.name, client.guid))
            except Exception, err:
                client.message('Error, server replied %s' % err)
        else:
            try:
                # input[0] is the player id
                sclient = self._adminPlugin.findClientPrompt(input[0], client)
                if sclient:
                    cmd.sayLoudOrPM(client, '%s: %s' % (sclient.name, sclient.guid))
            except Exception, err:
                client.message('Error, server replied %s' % err)
        
        
    def cmd_pakill(self, data, client, cmd=None):
        """\
        <name> <reason> - kill a player
        """
        m = self._adminPlugin.parseUserCmd(data)
        if not m:
            client.message('Invalid data, try !help pakill')
        else:
            cid, keyword = m
            reason = self._adminPlugin.getReason(keyword)
    
            if not reason and client.maxLevel < self._adminPlugin.config.getint('settings', 'noreason_level'):
                client.message('ERROR: You must supply a reason')
            else:
                sclient = self._adminPlugin.findClientPrompt(cid, client)
                if sclient:
                    self.console.saybig('%s was terminated by server admin' % sclient.name)
                    try:
                        self.console.write(('admin kill "%s"' % sclient.name))
                        if reason:
                            self.console.say('%s was terminated by server admin for : %s' % (sclient.name, reason))
                    except Exception, err:
                        client.message('Error, server replied %s' % err)
     

    def cmd_pachangeteam(self, data, client, cmd=None):
        """\
        [<name>] - change a player to the other team
        """
        input = self._adminPlugin.parseUserCmd(data)
        if not input:
            client.message('Invalid data, try !help pachangeteam')
        else:
            # input[0] is the player id
            sclient = self._adminPlugin.findClientPrompt(input[0], client)
            if sclient:
                try:
                    self.console.write('admin forceteamswitch "%s"' % sclient.name)
                    cmd.sayLoudOrPM(client, '%s forced to swap teams' % sclient.name)
                except Exception, err:
                    client.message('Error, server replied %s' % err)
        
        
    def cmd_paspectate(self, data, client, cmd=None):
        """\
        [<name>] - move a player to spectate
        """
        input = self._adminPlugin.parseUserCmd(data)
        if not input:
            client.message('Invalid data, try !help paspectate')
        else:
            # input[0] is the player id
            sclient = self._adminPlugin.findClientPrompt(input[0], client)
            if sclient:
                try:
                    self.console.write('admin makespectate "%s"' % sclient.name )
                    cmd.sayLoudOrPM(client, '%s forced to spectate' % sclient.name)
                except Exception, err:
                    client.message('Error, server replied %s' % err)
        
    def cmd_pamatch(self, data, client, cmd=None): 
        """\
        Set server match mode on/off
        (You can safely use the command without the 'pa' at the beginning)
        """
        if not data or str(data).lower() not in ('on','off'):
            client.message('Invalid or missing data, expecting "on" or "off"')
            return False
        else:
            if data.lower() == 'on':
                
                self._matchmode = True
                self._enableTeamBalancer = False
                
                for e in self._match_plugin_disable:
                    self.debug('Disabling plugin %s' %e)
                    plugin = self.console.getPlugin(e)
                    if plugin:
                        plugin.disable()
                        client.message('plugin %s disabled' % e)
                
                self.console.say('match mode: ON')
                if self._matchManager:
                    self._matchManager.stop()
                self._matchManager = MatchManager(self)
                self._matchManager.initMatch()

            elif data.lower() == 'off':
                self._matchmode = False
                if self._matchManager:
                    self._matchManager.stop()
                self._matchManager = None
                
                # enable plugins
                for e in self._match_plugin_disable:
                    self.debug('enabling plugin %s' %e)
                    plugin = self.console.getPlugin(e)
                    if plugin:
                        plugin.enable()
                        client.message('plugin %s enabled' % e)

                self.console.say('match mode: OFF')
                
#    def _changeMode(self, data, client, cmd=None, mode=None):
#        if mode is None:
#            self.error('mode cannot be None')
#        elif mode not in ('CONQUEST', 'RUSH', 'SQDM', 'SQRUSH'):
#            self.error('invalid game mode %s' % mode)
#        else:
#            try:
#                self.console.write(('admin.setPlaylist', mode))
#                client.message('Server playlist changed to %s' % mode)
#                client.message('type !map <some map> to change server mode now')
#            except Exception, err:
#                client.message('Failed to change game mode. Server replied with: %s' % err)
#
#    def cmd_paconquest(self, data, client, cmd=None):
#        """\
#        change server mode to CONQUEST
#        """
#        self._changeMode(data, client, cmd, mode='CONQUEST')
#
#    def cmd_parush(self, data, client, cmd=None):
#        """\
#        change server mode to RUSH
#        """
#        self._changeMode(data, client, cmd, mode='RUSH')
#
#    def cmd_pasqdm(self, data, client, cmd=None):
#        """\
#        change server mode to SQDM
#        """
#        self._changeMode(data, client, cmd, mode='SQDM')
#
#    def cmd_pasqrush(self, data, client, cmd=None):
#        """\
#        change server mode to SQRUSH
#        """
#        self._changeMode(data, client, cmd, mode='SQRUSH')
        
      
                
        
##################################################################################################  

#    def parseUserCmd(self, cmd, req=False):
#        """Parse command arguments to extract a player id as a first paramenter
#        from the other params
#        """
#        m = re.match(self._parseUserCmdRE, cmd)
#
#        if m:
#            cid = m.group('cid')
#            parms = m.group('parms')
#
#            if req and not len(parms): return None
#
#            if cid[:1] == "'" and cid[-1:] == "'":
#                cid = cid[1:-1]
#
#            return (cid, parms)
#        else:
#            return None
        
    def onClientAuth(self, data, client):
        #store the time of teamjoin for autobalancing purposes 
        client.setvar(self, 'teamtime', self.console.time())


    def onTeamChange(self, data, client):
        #store the time of teamjoin for autobalancing purposes 
        client.setvar(self, 'teamtime', self.console.time())
        self.verbose('Client variable teamtime set to: %s' % client.var(self, 'teamtime').value)
        
        if self._enableTeamBalancer:
            
            if self.console.time() < self._ignoreBalancingTill:
                return
            
            if client.team in (b3.TEAM_SPEC, b3.TEAM_UNKNOWN):
                return
            
            # get teams
            team1players, team2players = self.getTeams()
            
            # if teams are uneven by one or even, then stop here
            if abs(len(team1players) - len(team2players)) <= 1:
                return
            
            biggestteam = team1players
            if len(team2players) > len(team1players):
                biggestteam = team2players
            
            # has the current player gone contributed to making teams uneven ?
            if client.name in biggestteam:
                self.debug('%s has contributed to unbalance the teams')
                client.message('do not make teams unbalanced')
                try:
                    self.console.write('admin forceteamswitch "%s"' % client.name)
                except Exception, err:
                    self.warning('Error, server replied %s' % err)
             
    def onVoteStart(self, event):
        self._currentVote = event
        if event.data.lower() in ('kick', 'kickban') and event.client \
            and event.target and event.target.maxLevel >= self._auto_unban_level \
            and event.target.maxLevel > event.client.maxLevel:
                if event.target.maxLevel == 100:
                    ## voting ban against superadmin is bad
                    duration = self._adminPlugin.config.getDuration('settings', 'ban_duration')
                    event.client.tempban(duration=duration, reason="do not call vote against admin")
                else:
                    event.client.warn(duration="2d", warning="do not call vote against admin", keyword="STUPID_VOTE")
            
    def onVoteEnd(self, event):
        """
        {'yesvotes': 8, 'percentfor': 0.8, 'voteresult': failed/passed}
        """
        if self._currentVote.data.lower() == 'kickban' and event.data['voteresult'].lower() == "passed":
            votecaller = self._currentVote.client
            votetarget = self._currentVote.target
            if votecaller and votetarget:
                if votetarget.maxLevel < self._auto_unban_level:
                    self.info("%s (%s) is in a lower group than %s, vote allowed", votetarget, votetarget.maxLevel, self._auto_unban_level)
                elif votecaller.maxLevel > votetarget.maxLevel:
                    self.info("%s (%s) is in a higher group than %s (%s), vote allowed", votecaller, votecaller.maxLevel, votetarget, votetarget.maxLevel)
                else:
                    self.info("%s (%s) cannot vote ban %s (%s), vote cancelled", votecaller, votecaller.maxLevel, votetarget, votetarget.maxLevel)
                    votetarget.unban(reason="stupid vote auto unbanner", silent=True)
   
                
    def teambalance(self):
        # get teams
        team1players, team2players = self.getTeams()

        # if teams are uneven by one or even, then stop here
        gap = abs(len(team1players) - len(team2players))
        if gap <= 1:
            self.verbose('Teambalance: Teams are balanced, T1: %s, T2: %s (diff: %s)' %(len(team1players), len(team2players), gap))
            return

        howManyMustSwitch = int(gap / 2)
        bigTeam = b3.TEAM_RED
        smallTeam = b3.TEAM_BLUE
        if len(team2players) > len(team1players):
            bigTeam = b3.TEAM_BLUE
            smallTeam = b3.TEAM_RED

        self.verbose('Teambalance: Teams are NOT balanced, T1: %s, T2: %s (diff: %s)' %(len(team1players), len(team2players), gap))
        self.console.saybig('Autobalancing Teams!')

        ## we need to change team for howManyMustSwitch players from bigteam
        playerTeamTimes = {}
        clients = self.console.clients.getList()
        for c in clients:
            if c.team == bigTeam:
                playerTeamTimes[c.cid] = c.var(self, 'teamtime', self.console.time()).value

        self.debug('playerTeamTimes: %s' % playerTeamTimes)
        sortedPlayersTeamTimes = sorted(playerTeamTimes.iteritems(), key=lambda (k,v):(v,k), reverse=True)
        self.debug('sortedPlayersTeamTimes: %s' % sortedPlayersTeamTimes)

        for c, teamtime in sortedPlayersTeamTimes[:howManyMustSwitch]:
            try:
                self.debug('forcing %s to the other team' % c)
                self.console.write('admin forceteamswitch "%s"' % c)
            except Exception, err:
                self.error(err)
                
                    
    def getTeams(self):
        """Return two lists containing the names of players from both teams"""
        team1players = []
        team2players = []
        clients = self.console.clients.getList()
        for c in clients:
            if c.team == b3.TEAM_RED:
                team1players.append(c.cid)
            elif c.team == b3.TEAM_BLUE:
                team2players.append(c.cid)
        return team1players, team2players


################################################################################## 
import threading
class MatchManager:
    plugin = None
    _adminPlugin = None
    console = None
    playersReady = {}
    countDown = 10
    running = True
    timer = None
    countdownStarted = None
    
    def __init__(self, plugin):
        self.plugin = plugin
        self.console = plugin.console
        self._adminPlugin = self.console.getPlugin('admin')
        if not self._adminPlugin:
            # something is wrong, can't start without admin plugin
            raise Exception('Could not find admin plugin')
    
    def stop(self):
        try: self.timer.cancel()
        except: pass
        self.running = False
        self.unregisterCommandReady()
        
    def initMatch(self):
        for c in self.console.clients.getList():
            c.setvar(self.plugin, 'ready', False)
        self.countdownStarted = False
        self.registerCommandReady()
        self.console.saybig('MATCH starting soon !!')
        self.console.say('ALL PLAYERS : type !ready when you are ready')
        self.console.saybig('ALL PLAYERS : type !ready when you are ready')
        self.timer = threading.Timer(10.0, self._checkIfEveryoneIsReady)
        self.timer.start()
    
    def registerCommandReady(self):
        self._adminPlugin.registerCommand(self.plugin, 'ready', 0, self.cmd_ready)
    
    def unregisterCommandReady(self):
        # unregister the !ready command
        try:
            cmd = self._adminPlugin._commands['ready']
            if cmd.plugin == self.plugin:
                self.plugin.debug('unregister !ready command')
                del self._adminPlugin._commands['ready']
        except KeyError:
            pass
    
    def yellToClient(self, message, duration, client):
        """We need this to bypass the message queue managed by the HF parser"""
        self.console.write(('admin.yell', message, duration, 'player', client.cid))

    def _checkIfEveryoneIsReady(self):
        self.console.debug('checking if all players are ready')
        isAllPlayersReady = True
        waitingForPlayers = []
        for c in self.console.clients.getList():
            isReady = c.var(self.plugin, 'ready', False).value
            self.plugin.debug('is %s ready ? %s' % (c.cid, isReady))
            if isReady is False:
                waitingForPlayers.append(c)
                self.yellToClient('we are waiting for you. type !ready', 10000, c)
                isAllPlayersReady = False
    
        if len(waitingForPlayers) > 0 and len(waitingForPlayers) <= 6:
            self.console.say('waiting for %s' % ', '.join([c.cid for c in waitingForPlayers]))
        
        try: self.timer.cancel()
        except: pass
        
        if isAllPlayersReady is True:
            self.console.say('All players are ready, starting count down')
            self.countDown = 10
            self.countdownStarted = True
            self.timer = threading.Timer(0.9, self._countDown)
        else:
            self.timer = threading.Timer(10.0, self._checkIfEveryoneIsReady)
            
        if self.running:
            self.timer.start()

    def _countDown(self):
        self.plugin.debug('countdown: %s' % self.countDown)
        if self.countDown > 0:
            self.console.write(('admin.yell', 'MATCH STARTING IN %s' % self.countDown, 900, 'all'))
            self.countDown -= 1
            if self.running:
                self.timer = threading.Timer(1.0, self._countDown)
                self.timer.start()
        else:    
            # make sure to have a brief big text
            self.console.write(('admin.yell', 'FIGHT !!!', 6000, 'all'))
            self.console.say('Match started. GL & HF')
            self.console.write(('admin.restartMap',))
            self.stop()

    def cmd_ready(self, data, client, cmd=None): 
        """\
        Notify other teams you are ready to start the match
        """
        self.plugin.debug('MatchManager::ready(%s)' % client.cid)
        if self.countdownStarted:
            client.message('Count down already started. You cannot change your ready state')
        else:
            wasReady = client.var(self.plugin, 'ready', False).value
            if wasReady:
                client.setvar(self.plugin, 'ready', False)
                self.yellToClient('You are not ready anymore', 3000, client)
                client.message('You are not ready anymore')
            else:
                client.setvar(self.plugin, 'ready', True)
                self.yellToClient('You are now ready', 3000, client)
                client.message('You are now ready')
            self._checkIfEveryoneIsReady()





if __name__ == '__main__':
    import time
    
    from b3.fake import fakeConsole, FakeClient
    fakeConsole.gameName = 'homefront'

    fakeConsole.Events.createEvent('EVT_CLIENT_VOTE_START', 'Client Vote Start')
    fakeConsole.Events.createEvent('EVT_CLIENT_VOTE', 'Client Vote')
    fakeConsole.Events.createEvent('EVT_SERVER_VOTE_END', 'Server Vote End')
    
    def callBanVote(self, target):
        print "\n%s calls a ban vote against %s" % (self.name, target.name)
        self.console.queueEvent(b3.events.Event(b3.events.EVT_CLIENT_VOTE_START, data="KickBan", client=self, target=target))
    FakeClient.callBanVote = callBanVote
    
    def callKickVote(self, target):
        print "\n%s calls a kick vote against %s" % (self.name, target.name)
        self.console.queueEvent(b3.events.Event(b3.events.EVT_CLIENT_VOTE_START, data="Kick", client=self, target=target))
    FakeClient.callKickVote = callKickVote
    
    from b3.fake import joe, simon, moderator, superadmin
            
    from b3.config import XmlConfigParser
    conf = XmlConfigParser()
    conf.setXml("""
    <configuration plugin="poweradminhf">
        <settings name="commands">
            <set name="paversion">1</set>

            <set name="pachangeteam-ct">60</set>
            <set name="paspectate-spectate">60</set>
            <set name="pakill-kill">60</set>
            <set name="payell-yell">20</set>
            <set name="paident-id">20</set>
            <set name="panextmap-endmap">20</set>

            <!-- Homefronts Autobalancer on/off switch-->
            <set name="paautobalance-autobalance">40</set>

            <!-- Poweradmins teambalancer on/off switch -->
            <set name="pateambalance">40</set>
            <set name="pateams-teams">20</set>

            <!-- set match mode on/off. Will wait for teams leaders to type !ready
                and then start a count down -->
            <set name="pamatch-match">20</set>
        </settings>

        <!-- Poweradmins teambalancer -->
        <settings name="teambalancer">
            <!-- on/off - if 'on' the bot will switch players making teams unbalanced -->
            <set name="enabled">off</set>
        </settings>

        <!-- Stupid vote protector -->
        <settings name="voteprotector">
            <!-- if an admin above auto_unban_level is banned by vote from a
            player of lower level, then he will be automatically unbanned -->
            <set name="auto_unban_level">40</set>
        </settings>

        <pamatch_plugins_disable>
            <!-- The Plugins that need to be disabled during matchmode -->
            <plugin>spree</plugin>
            <plugin>adv</plugin>
            <plugin>tk</plugin>
            <plugin>pingwatch</plugin>
        </pamatch_plugins_disable>
    </configuration>
    """)

    
    ## create an instance of the plugin to test
    p = PoweradminhfPlugin(fakeConsole, conf)
    p.onStartup()

    joe.connects('Joe')
    simon.connects('Simon')
    moderator.connects('Mod')
    
    def testMatch1():
        print """-----------------------
        usual scenario"""
        moderator.says('!match on')
        time.sleep(1)
        
        joe.says('!ready')
        time.sleep(1)
    
        simon.says('!ready')
        time.sleep(1)
    
        moderator.says('!ready')
        time.sleep(15)
        p._matchManager.stop()
        
    def testMatch2():
        print """-----------------------
        joe types !ready a second time"""
        moderator.says('!match on')
        time.sleep(1)
        
        joe.says('!ready')
        time.sleep(1)
    
        simon.says('!ready')
        time.sleep(1)

        joe.says('!ready')
        time.sleep(1)
    
        moderator.says('!ready')
        time.sleep(15)
        
        p._matchManager.stop()
        
    def testMatch3():
        print """-----------------------
        moderator types !match off"""
        moderator.says('!match on')
        time.sleep(1)
        
        joe.says('!ready')
        time.sleep(1)
    
        simon.says('!ready')
        time.sleep(1)
    
        moderator.says('!match off')
        time.sleep(15)
        
        print "p._matchManager : %s" % p._matchManager

    def testMatch4():
        print """-----------------------
        moderator types !match on a second time"""
        moderator.says('!match on')
        time.sleep(1)
        
        joe.says('!ready')
        time.sleep(1)
    
        simon.says('!ready')
        time.sleep(1)
    
        moderator.says('!match on')
        time.sleep(15)
        
        joe.says('!ready')
        time.sleep(1)
    
        simon.says('!ready')
        time.sleep(12)
        
        moderator.says('!ready')
        
        time.sleep(12)
        print "p._matchManager : %s" % p._matchManager
        
        
    def testMatch5():
        print """-----------------------
        a player got kicked"""
        p.console.PunkBuster = None
        
        moderator.says('!match on')
        time.sleep(1)
        
        joe.says('!ready')
        time.sleep(1)
    
        moderator.says('!ready')
        time.sleep(15)
        
        simon.kick('AFL')
        time.sleep(30)
        p._matchManager.stop()
        
    def testMatch6():
        print """-----------------------
        a player tries to type !ready after the count down started"""
        p.console.PunkBuster = None
        
        moderator.says('!match on')
        time.sleep(1)
        
        joe.says('!ready')
        time.sleep(1)
    
        moderator.says('!ready')
        time.sleep(1)
        
        simon.says('!ready')
        time.sleep(5)
        
        simon.says('!ready')
        time.sleep(10)
        p._matchManager.stop()

    def testServerModeChange():
        superadmin.connects('Superman')
        superadmin.says('!parush')
        superadmin.says('!rush')
        superadmin.says('!pasqrush')
        superadmin.says('!pasqru')
        superadmin.says('!paconquest')
        superadmin.says('!conq')
        superadmin.says('!pasqrush')
        superadmin.says('!sqru')
    
    def testAutoUnban():
        print('-'*40)
        joe.callBanVote(moderator)
        time.sleep(1)
        fakeConsole.queueEvent(fakeConsole.getEvent('EVT_SERVER_VOTE_END',data={'yesvotes': 2, 'percentfor': 1.0, 'voteresult': 'Passed'}))
        time.sleep(2)
        
        p._auto_unban_level = 2
        print('-'*40)
        joe.callBanVote(moderator)
        time.sleep(1)
        fakeConsole.queueEvent(fakeConsole.getEvent('EVT_SERVER_VOTE_END',data={'yesvotes': 2, 'percentfor': 1.0, 'voteresult': 'Passed'}))
        time.sleep(2)
        
        
        print('-'*40)
        joe.callKickVote(moderator)
        time.sleep(1)
        fakeConsole.queueEvent(fakeConsole.getEvent('EVT_SERVER_VOTE_END',data={'yesvotes': 2, 'percentfor': 1.0, 'voteresult': 'Passed'}))
        time.sleep(2)
        
        print('-'*40)
        superadmin.connects("god")
        joe.callBanVote(superadmin)
        time.sleep(1)
        fakeConsole.queueEvent(fakeConsole.getEvent('EVT_SERVER_VOTE_END',data={'yesvotes': 2, 'percentfor': 1.0, 'voteresult': 'Passed'}))
        time.sleep(2)
        
    #testMatch6()
    testAutoUnban()
