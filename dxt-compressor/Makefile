CFLAGS+=-pipe -Wall
GCC=gcc
MINGW=x86_64-w64-mingw32-gcc
LD_MINGW=x86_64-w64-mingw32-ld

LIBS=-lm

OS=$(shell uname -s)

ifneq (,$(findstring Linux,$(TARGET)))
EXT=
CC=$(GCC)
LIBS+=-lGL -lGLU -lX11
endif

ifneq (,$(findstring CYGWIN,$(TARGET)))
EXT=.exe
CC=$(MINGW)
LDFLAGS+=-L./glew/lib/Release/x64 -I./glew/include
LD=$(LD_MINGW)
LIBS+=-lglew32 -lopengl32 -lgdi32
endif

$(info $(LIBS))

ifneq (,$(findstring MinGW,$(TARGET)))
EXT=.exe
CC=$(MINGW)
LDFLAGS+=-L./glew/lib/Release/x64 -I./glew/include
LD=$(LD_MINGW)
LIBS+=-lglew32 -lopengl32 -lgdi32
endif

ifeq ($(DXT_TARGET),release)
CFLAGS+=-O2
$(info adding release cflags...)
else ifeq ($(DXT_TARGET),debug)
$(info adding debug cflags...)
CFLAGS+=-O0
endif

TARGET_RELEASE=dxtcompressor$(EXT)
TARGET_DEBUG=dxtcompressor-debug$(EXT)

SRCS=main.c
OBJS=$(SRCS:.c=.o)

ifdef VERBOSE
Q=
else
Q=@
endif

all: $(TARGET_DEBUG) $(TARGET_RELEASE)

$(TARGET_DEBUG): $(OBJS)
	$(Q)echo "[LD]\t$@"
	$(Q)$(CC) $(LDFLAGS) $(OBJS) $(LIBS) -o $(TARGET_DEBUG)

$(TARGET_RELEASE): $(OBJS)
	$(Q)echo "[LD]\t$@"
	$(Q)$(CC) $(LDFLAGS) $(OBJS) $(LIBS) -o $(TARGET_RELEASE)
	
debug: $(TARGET_DEBUG)
release: $(TARGET_RELEASE)

clean:
	rm -f *.o $(TARGET)

install: all
	$(GIMPTOOL) --install-bin $(TARGET)

.c.o:
	$(Q)echo "[CC]\t$<"
	$(Q)$(CC) -c $(CFLAGS) -o $@ $<

main.o: main.c

