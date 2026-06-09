# -*- coding: utf-8 -*-
from helpers import getClientLanguage
from Singleton import Singleton


EN = {
  'title': 'Vegetation',
  'showPositions': 'Show positions (30m)',
  'showColliders': 'Show collisions',
  'onlyCamouflaging': '  Only camouflaging',
  'message.showColliders': 'Show collisions: ',
  'message.onlyCamouflaging': 'Only camouflaging: ',
  'message.True': 'On',
  'message.False': 'Off',
  'message.modUnavailable': 'Mod unavailable in this battle mode',
}

RU = {
  'title': 'Растительность',
  'showPositions': 'Отображать позиции (30м)',
  'showColliders': 'Отображать колижены',
  'onlyCamouflaging': '  Только маскирующие',
  'message.showColliders': 'Отображение колиженов: ',
  'message.onlyCamouflaging': 'Только маскирующие: ',
  'message.True': 'Вкл',
  'message.False': 'Выкл',
  'message.modUnavailable': 'Мод недоступен в этом режиме боя',
}


class I18n(Singleton):
  @staticmethod
  def instance():
    return I18n()

  def __init__(self):
    language = getClientLanguage()

    if language == 'ru':
      self.current_localizations = RU
    else:
      self.current_localizations = EN

  def t(self, key):
    if key in self.current_localizations:
      return self.current_localizations[key]
    return key
  
  def has(self, key):
    return key in self.current_localizations
  
  def translate(self, key):
    return self.t(key)
  
def t(key):
  return I18n.instance().t(key)

def prefix(prefix):
  return lambda key: t(prefix + '.' + key)

def has(key):
  return I18n.instance().has(key)
