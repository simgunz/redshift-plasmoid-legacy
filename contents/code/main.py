# -*- coding: utf-8 -*-
# redshift-plasmoid/contents/code/main.py

'''
Provides a configuration interface and a switch to start/stop Redshift daemon. 
Copyright (C) 2011 Diego Cristina
Copyright (C) 2012 Simone Gaiarin

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyKDE4.kdeui import *
from PyKDE4.plasma import Plasma
from PyKDE4.kdecore import KProcess, KSystemTimeZones, i18n
from PyKDE4 import plasmascript

import os
import subprocess
import signal

THEME = 'widgets/background'
ICON_PLASMOID = 'redshift'
ICON_STOPPED = 'redshift-status-off'
ICON_RUNNING = 'redshift-status-on'
# Default color temperature
DEFAULT_NIGHT = 3700
DEFAULT_DAY = 5500

class RedshiftApplet(plasmascript.Applet):

    def __init__(self, parent, args=None):
        plasmascript.Applet.__init__(self, parent)
        self.parent = parent

    def init(self):
        self.iconStopped = KIcon(ICON_STOPPED)
        self.iconRunning = KIcon(ICON_RUNNING)
        self.setHasConfigurationInterface(True)
        self.process = KProcess()
        self.dontStart = False
        self.restart = False
        # Set size of Plasmoid
        self.resize(100, 100)
        self.setMinimumSize(10,10)
        self.setAspectRatioMode(Plasma.KeepAspectRatio)
        self.setBackgroundHints(Plasma.Applet.DefaultBackground)
        self.theme = Plasma.Svg(self)
        self.theme.setImagePath(THEME)
        self.button = Plasma.IconWidget(self.parent)
        self.button.setIcon(self.iconStopped)
        self.layout = QGraphicsGridLayout(self.applet)
        self.layout.setContentsMargins(0,0,0,0)
        self.layout.addItem(self.button, 0, 0)        
        # Set the tooltip
        self.tooltip = Plasma.ToolTipContent()
        self.tooltip.setMainText(i18n('Redshift'))
        self.tooltip.setSubText(i18n('Click to toggle it on'))
        self.tooltip.setImage(self.iconStopped)
        Plasma.ToolTipManager.self().setContent(self.applet, self.tooltip)
        # Connect signals and slots
        self.button.clicked.connect(self.toggle)
        self.appletDestroyed.connect(self.destroy)
        self.process.finished.connect(self.toggle)
        # Load configuration
        self.configChanged()
        # Set the default latitude and longitude values in the
        # configuration file, so that the config dialog can read them
        if not (self.latitude or self.longitude):
            self.latitude = KSystemTimeZones.local().latitude()
            self.longitude = KSystemTimeZones.local().longitude()
            cfgGeneral = self.config().group("General")
            cfgGeneral.writeEntry('latitude',self.latitude)
            cfgGeneral.writeEntry('longitude',self.longitude)
        # Autolaunch
        if self.autolaunch:
            print('Autostarting Redshift')
            self.toggle()
            
    def configChanged(self):
        # Read the values from the configuration file, called automatically when configuration is changed
        cfgGeneral = self.config().group("General")        
        self.latitude = cfgGeneral.readEntry('latitude',0).toFloat()[0]
        self.longitude = cfgGeneral.readEntry('longitude',0).toFloat()[0]
        self.nighttemp = cfgGeneral.readEntry('nightTemp', DEFAULT_NIGHT).toInt()[0]
        self.daytemp = cfgGeneral.readEntry('dayTemp', DEFAULT_DAY).toInt()[0]
        self.smooth = cfgGeneral.readEntry('smooth', True).toBool()
        self.autolaunch = cfgGeneral.readEntry('autolaunch', False).toBool()
        gammaR = cfgGeneral.readEntry('gammaR', 1.00).toFloat()[0]
        gammaG = cfgGeneral.readEntry('gammaG', 1.00).toFloat()[0]
        gammaB = cfgGeneral.readEntry('gammaB', 1.00).toFloat()[0]        
        self.gamma = str("%.2f:%.2f:%.2f" % (gammaR, gammaG, gammaB))                     
        self.restartRedshift()
    
    def toggleStatus(self):
        if self.button.icon().name() == self.iconRunning.name():
            self.button.setIcon(self.iconStopped)
            self.tooltip.setImage(self.iconStopped)
            self.tooltip.setSubText(i18n('Click to toggle it on'))
        else:
            self.button.setIcon(self.iconRunning)
            self.tooltip.setImage(self.iconRunning)
            self.tooltip.setSubText(i18n('Click to toggle it off'))
        Plasma.ToolTipManager.self().setContent(self.applet, self.tooltip)
        
    def toggle(self):
        # Toggle Redshift on/off
        if self.process.state() == QProcess.Running:
            os.kill(int(self.process.pid()), signal.SIGUSR1)
        elif not self.dontStart:
            self.startRedshift()
        if not self.restart:
            self.toggleStatus()
        self.restart = False
        self.dontStart = False
            
    def startRedshift(self):
        """Start redshift if all conditions are satisfied
        
        Wait for any previous instance of Redshift launched by the applet to terminate,
        if redshift is launched outside the applet, notify the user and don't start Redshift
        """
        self.process.waitForFinished()
        if not subprocess.call(['pidof','redshift']):
            KNotification.event(KNotification.Notification, i18n('Redshift'),i18n('Another instance of Redshift is running. It must be closed before you can use this applet.'), KIcon(ICON_PLASMOID).pixmap(QSize(32,32)));
            return
        print('Starting Redshift with latitude %.1f, longitude %.1f, day temperature %d, night temperature %d, gamma ramp %s, smooth transition = %s' % (self.latitude, self.longitude, self.daytemp, self.nighttemp, self.gamma, ('yes' if self.smooth else 'no')))
        self.process.setShellCommand('%s -c /dev/null -l %.1f:%.1f -t %d:%d -g %s %s' % ('redshift', self.latitude, self.longitude, self.daytemp, self.nighttemp, self.gamma, ('-r' if not self.smooth else '')))
        self.process.start()
        
    def restartRedshift(self):
        """Terminate the redshift process and eventually restart it
        
        If Redshift is not running no signal is emitted so toggle is not called
        If Redshift is running, it is terminated, a signal is emitted and toggle is called:
            if Redshift was not active the flag dontStart is setted and no new process is started
            if Redshift was active it is started    
        """
        print 'Stopping Redshift'
        if (self.process.state() == QProcess.Running):
            self.restart = True
            if self.button.icon().name() == self.iconStopped.name():
                self.dontStart = True
        self.process.terminate()
    
    def destroy(self):
        # Kill redshift and clear any gamma correction
        self.process.kill()
        self.process.waitForFinished()
        subprocess.call(['redshift','-c','/dev/null','-x'])
        
def CreateApplet(parent):
    return RedshiftApplet(parent)
