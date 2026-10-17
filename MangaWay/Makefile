#---------------------------------------------------------------------------------
# Progetto MangaWay
#---------------------------------------------------------------------------------
TARGET      := MangaWay
LIBCTRU     := $(DEVKITPRO)/libctru

ARCH    := -march=armv6k -mtune=mpcore -mfloat-abi=hard -mfpu=vfpv2
# Configurazione pulita dei percorsi d'inclusione standard del 3DS
CFLAGS  := -g -Wall -O2 -mword-relocations -fomit-frame-pointer -ffunction-sections $(ARCH) -D__3DS__ -I$(LIBCTRU)/include -I$(DEVKITPRO)/portlibs/3ds/include
CXXFLAGS:= $(CFLAGS) -fno-rtti -std=gnu++11
LDFLAGS = -specs=3dsx.specs -g $(ARCH) -L$(LIBCTRU)/lib -L$(DEVKITPRO)/portlibs/3ds/lib

# Librerie collegate nell'ordine esatto richiesto dal linker
LIBS    := -lcitro2d -lcitro3d -lcurl -lmbedtls -lmbedx509 -lmbedcrypto -lz -lctru -lm

# IMPOSTIAMO ESPLICITAMENTE IL COMPILATORE E GLI STRUMENTI DEL 3DS
CXX        := $(DEVKITARM)/bin/arm-none-eabi-g++
3DSX_TOOL  := $(DEVKITPRO)/tools/bin/3dsxtool
MAKE_ROM   := /c/devkitPro/tools/bin/makerom.exe

all: $(TARGET).3dsx $(TARGET).cia

build/main.o: source/main.cpp
	@mkdir -p build
	$(CXX) $(CXXFLAGS) -c source/main.cpp -o build/main.o

$(TARGET).elf: build/main.o
	$(CXX) $(LDFLAGS) build/main.o $(LIBS) -o $(TARGET).elf

$(TARGET).3dsx: $(TARGET).elf
	@echo "Generazione del file 3DSX..."
	$(3DSX_TOOL) $(TARGET).elf $(TARGET).3dsx

$(TARGET).cia: $(TARGET).elf
	@echo "Generazione dell'icona 3DS..."
	@/opt/devkitpro/tools/bin/smdhtool --create "MangaWay" "Manga Reader" "Stefano" icon.png build/icon.smdh
	@echo "Generazione del file CIA..."
	$(MAKE_ROM) -f cia -o $(TARGET).cia -elf $(TARGET).elf -rsf MangaWay.rsf -icon build/icon.smdh

clean:
	@echo "Pulizia dei file temporanei..."
	@rm -rf build $(TARGET).elf $(TARGET).3dsx $(TARGET).cia
	@echo "Pulizia completata!"

.PHONY: all clean

