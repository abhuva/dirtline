TARGET := dustline
BUILD := build
LIBBUTANO := .tools/butano/butano
PYTHON := python3
SOURCES := src
INCLUDES := include
DATA :=
# Only converted BMPs are Butano inputs; source PNGs may use arbitrary names.
GRAPHICS := $(wildcard graphics/*.bmp)
# Butano's default object list expects directories even though its importer
# also accepts files. Supply the matching object inputs explicitly.
override GRAPHICSFILES := $(notdir $(GRAPHICS))
AUDIO := audio
AUDIOBACKEND := maxmod
AUDIOTOOL :=
DMGAUDIO :=
DMGAUDIOBACKEND := null
ROMTITLE := DUSTLINE
ROMCODE := DUST
USERFLAGS :=
USERCXXFLAGS :=
USERASFLAGS :=
USERLDFLAGS :=
USERLIBDIRS :=
USERLIBS :=
DEFAULTLIBS :=
STACKTRACE :=
USERBUILD :=
EXTTOOL :=
ifndef LIBBUTANOABS
export LIBBUTANOABS := $(realpath $(LIBBUTANO))
endif
include $(LIBBUTANOABS)/butano.mak
