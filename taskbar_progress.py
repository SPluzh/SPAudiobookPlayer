"""
Модуль для отображения прогресса в кнопке таскбара Windows
Требует: pip install comtypes
"""
import sys
from translations import tr

COMTYPES_AVAILABLE = False

if sys.platform == 'win32':
    try:
        import ctypes
        from ctypes import POINTER, HRESULT, byref
        from ctypes.wintypes import HWND
        import comtypes
        from comtypes import IUnknown, GUID, COMMETHOD
        import comtypes.client
        COMTYPES_AVAILABLE = True
    except ImportError:
        print("comtypes не установлен. Установите: pip install comtypes")


if COMTYPES_AVAILABLE:
    # Определяем интерфейс ITaskbarList3
    class ITaskbarList(IUnknown):
        _iid_ = GUID('{56FDF342-FD6D-11d0-958A-006097C9A090}')
        _methods_ = [
            COMMETHOD([], HRESULT, 'HrInit'),
            COMMETHOD([], HRESULT, 'AddTab', (['in'], HWND, 'hwnd')),
            COMMETHOD([], HRESULT, 'DeleteTab', (['in'], HWND, 'hwnd')),
            COMMETHOD([], HRESULT, 'ActivateTab', (['in'], HWND, 'hwnd')),
            COMMETHOD([], HRESULT, 'SetActiveAlt', (['in'], HWND, 'hwnd')),
        ]

    class ITaskbarList2(ITaskbarList):
        _iid_ = GUID('{602D4995-B13A-429b-A66E-1935E44F4317}')
        _methods_ = [
            COMMETHOD([], HRESULT, 'MarkFullscreenWindow',
                      (['in'], HWND, 'hwnd'),
                      (['in'], ctypes.c_int, 'fFullscreen')),
        ]

    # Структуры для кнопок
    class THUMBBUTTON(ctypes.Structure):
        _fields_ = [
            ('dwMask', ctypes.c_uint),
            ('iId', ctypes.c_uint),
            ('iBitmap', ctypes.c_uint),
            ('hIcon', ctypes.c_void_p),
            ('szTip', ctypes.c_wchar * 260),
            ('dwFlags', ctypes.c_uint),
        ]

    # Константы для кнопок
    THB_BITMAP = 0x1
    THB_ICON = 0x2
    THB_TOOLTIP = 0x4
    THB_FLAGS = 0x8
    
    THBF_ENABLED = 0x0
    THBF_DISABLED = 0x1
    THBF_DISMISSONCLICK = 0x2
    THBF_NOBACKGROUND = 0x4
    THBF_HIDDEN = 0x8
    
    # ID кнопок
    THUMBBUTTON_PREV = 0
    THUMBBUTTON_PLAYPAUSE = 1
    THUMBBUTTON_NEXT = 2
    THUMBBUTTON_REWIND = 3
    THUMBBUTTON_FORWARD = 4

    class ITaskbarList3(ITaskbarList2):
        _iid_ = GUID('{ea1afb91-9e28-4b86-90e9-9e9f8a5eefaf}')
        _methods_ = [
            COMMETHOD([], HRESULT, 'SetProgressValue',
                      (['in'], HWND, 'hwnd'),
                      (['in'], ctypes.c_ulonglong, 'ullCompleted'),
                      (['in'], ctypes.c_ulonglong, 'ullTotal')),
            COMMETHOD([], HRESULT, 'SetProgressState',
                      (['in'], HWND, 'hwnd'),
                      (['in'], ctypes.c_int, 'tbpFlags')),
            COMMETHOD([], HRESULT, 'RegisterTab',
                      (['in'], HWND, 'hwndTab'),
                      (['in'], HWND, 'hwndMDI')),
            COMMETHOD([], HRESULT, 'UnregisterTab',
                      (['in'], HWND, 'hwndTab')),
            COMMETHOD([], HRESULT, 'SetTabOrder',
                      (['in'], HWND, 'hwndTab'),
                      (['in'], HWND, 'hwndInsertBefore')),
            COMMETHOD([], HRESULT, 'SetTabActive',
                      (['in'], HWND, 'hwndTab'),
                      (['in'], HWND, 'hwndMDI'),
                      (['in'], ctypes.c_uint, 'dwReserved')),
            COMMETHOD([], HRESULT, 'ThumbBarAddButtons',
                      (['in'], HWND, 'hwnd'),
                      (['in'], ctypes.c_uint, 'cButtons'),
                      (['in'], POINTER(THUMBBUTTON), 'pButtons')),
            COMMETHOD([], HRESULT, 'ThumbBarUpdateButtons',
                      (['in'], HWND, 'hwnd'),
                      (['in'], ctypes.c_uint, 'cButtons'),
                      (['in'], POINTER(THUMBBUTTON), 'pButtons')),
            COMMETHOD([], HRESULT, 'ThumbBarSetImageList',
                      (['in'], HWND, 'hwnd'),
                      (['in'], ctypes.c_void_p, 'himl')),
            COMMETHOD([], HRESULT, 'SetOverlayIcon',
                      (['in'], HWND, 'hwnd'),
                      (['in'], ctypes.c_void_p, 'hIcon'),
                      (['in'], ctypes.c_wchar_p, 'pszDescription')),
            COMMETHOD([], HRESULT, 'SetThumbnailTooltip',
                      (['in'], HWND, 'hwnd'),
                      (['in'], ctypes.c_wchar_p, 'pszTip')),
            COMMETHOD([], HRESULT, 'SetThumbnailClip',
                      (['in'], HWND, 'hwnd'),
                      (['in'], ctypes.c_void_p, 'prcClip')),
        ]

    # CLSID TaskbarList
    CLSID_TaskbarList = GUID('{56FDF344-FD6D-11d0-958A-006097C9A090}')


class TaskbarProgress:
    """
    Класс для отображения прогресса в кнопке таскбара Windows.
    """
    
    # Константы состояний
    TBPF_NOPROGRESS = 0x0
    TBPF_INDETERMINATE = 0x1
    TBPF_NORMAL = 0x2
    TBPF_ERROR = 0x4
    TBPF_PAUSED = 0x8
    
    def __init__(self):
        self.hwnd = None
        self.taskbar = None
        self._initialized = False
        self._current_state = self.TBPF_NOPROGRESS
        
        if sys.platform == 'win32' and COMTYPES_AVAILABLE:
            self._init_taskbar()
    
    def _init_taskbar(self):
        """Инициализация COM-интерфейса ITaskbarList3"""
        try:
            # Создаём COM-объект и получаем интерфейс ITaskbarList3
            taskbar = comtypes.client.CreateObject(
                CLSID_TaskbarList,
                interface=ITaskbarList3
            )
            
            # Инициализируем
            taskbar.HrInit()
            
            self.taskbar = taskbar
            self._initialized = True
            
        except Exception as e:
            print(f"Не удалось инициализировать TaskbarProgress: {e}")
            self._initialized = False
    
    @property
    def is_available(self) -> bool:
        """Проверяет, доступен ли функционал таскбара"""
        return self._initialized and self.hwnd is not None
    
    def set_hwnd(self, hwnd: int):
        """
        Устанавливает дескриптор окна.
        Вызывайте после показа окна (в showEvent).
        """
        self.hwnd = hwnd
    
    def set_progress(self, current: float, total: float):
        """Устанавливает значение прогресса"""
        if not self.is_available:
            return
        
        try:
            # Преобразуем в целые числа для API
            current_int = max(0, int(current))
            total_int = max(1, int(total))  # Избегаем деления на 0
            
            self.taskbar.SetProgressValue(self.hwnd, current_int, total_int)
            
        except Exception:
            pass
    
    def set_progress_percent(self, percent: int):
        """Устанавливает прогресс в процентах (0-100)"""
        self.set_progress(percent, 100)
    
    def set_state(self, state: int):
        """
        Устанавливает состояние прогресс-бара.
        state: Одна из констант TBPF_*
        """
        if not self.is_available:
            return
        
        try:
            self.taskbar.SetProgressState(self.hwnd, state)
            self._current_state = state
        except Exception:
            pass
    
    def set_normal(self):
        self.set_state(self.TBPF_NORMAL)
    
    def set_paused(self):
        self.set_state(self.TBPF_PAUSED)
    
    def set_error(self):
        self.set_state(self.TBPF_ERROR)
    
    def set_indeterminate(self):
        self.set_state(self.TBPF_INDETERMINATE)
    
    def clear(self):
        """Скрывает прогресс-бар в таскбаре"""
        self.set_state(self.TBPF_NOPROGRESS)
    
    def update_for_playback(self, is_playing: bool, current: float, total: float):
        """
        Комплексное обновление для аудиоплеера.
        """
        if not self.is_available:
            return
        
        # Устанавливаем состояние в зависимости от воспроизведения
        new_state = self.TBPF_NORMAL if is_playing else self.TBPF_PAUSED
        
        if new_state != self._current_state:
            self.set_state(new_state)
        
        # Обновляем прогресс
        self.set_progress(current, total)


class TaskbarThumbnailButtons:
    """Управление кнопками в превью панели задач Windows"""
    
    def __init__(self, taskbar_interface, hwnd: int, icons_dir):
        self.taskbar = taskbar_interface
        self.hwnd = hwnd
        self.icons_dir = icons_dir
        self._buttons_added = False
        self._is_playing = False
        self._buttons_cache = None  # Ссылка на массив кнопок чтобы не удалил GC
        
    def _get_hicon(self, name: str):
        """Пытается загрузить иконку и вернуть HICON"""
        # Сначала пробуем ICO
        ico_path = self.icons_dir / f"{name}.ico"
        if ico_path.exists():
            return ctypes.windll.user32.LoadImageW(
                0, str(ico_path), 1, 64, 64, 0x10
            )
        
        # Если нет ICO, пробуем PNG (может не сработать через LoadImageW)
        png_path = self.icons_dir / f"{name}.png"
        if png_path.exists():
            return ctypes.windll.user32.LoadImageW(
                0, str(png_path), 1, 64, 64, 0x10
            )
            
        return None

    def add_buttons(self):
        """Добавляет кнопки при первом показе окна"""
        if not COMTYPES_AVAILABLE or not self.taskbar or self._buttons_added:
            return
            
        try:
            # Создаём массив из 5 кнопок
            buttons = (THUMBBUTTON * 5)()
            self._buttons_cache = buttons  # Keep reference
            
            # 1. Кнопка Previous (ID=0)
            buttons[0].dwMask = THB_ICON | THB_TOOLTIP | THB_FLAGS
            buttons[0].iId = THUMBBUTTON_PREV
            buttons[0].hIcon = self._get_hicon('prev')
            buttons[0].szTip = tr('taskbar.prev')
            buttons[0].dwFlags = THBF_ENABLED
            
            # 2. Кнопка Rewind (ID=3)
            buttons[1].dwMask = THB_ICON | THB_TOOLTIP | THB_FLAGS
            buttons[1].iId = THUMBBUTTON_REWIND
            buttons[1].hIcon = self._get_hicon('rewind_10')
            buttons[1].szTip = tr('taskbar.rewind')
            buttons[1].dwFlags = THBF_ENABLED
            
            # 3. Кнопка Play/Pause (ID=1)
            buttons[2].dwMask = THB_ICON | THB_TOOLTIP | THB_FLAGS
            buttons[2].iId = THUMBBUTTON_PLAYPAUSE
            buttons[2].hIcon = self._get_hicon('play')
            buttons[2].szTip = tr('taskbar.play')
            buttons[2].dwFlags = THBF_ENABLED
            
            # 4. Кнопка Forward (ID=4)
            buttons[3].dwMask = THB_ICON | THB_TOOLTIP | THB_FLAGS
            buttons[3].iId = THUMBBUTTON_FORWARD
            buttons[3].hIcon = self._get_hicon('forward_10')
            buttons[3].szTip = tr('taskbar.forward')
            buttons[3].dwFlags = THBF_ENABLED
            
            # 5. Кнопка Next (ID=2)
            buttons[4].dwMask = THB_ICON | THB_TOOLTIP | THB_FLAGS
            buttons[4].iId = THUMBBUTTON_NEXT
            buttons[4].hIcon = self._get_hicon('next')
            buttons[4].szTip = tr('taskbar.next')
            buttons[4].dwFlags = THBF_ENABLED
            
            # Добавляем кнопки. Важно: используем ctypes.cast для получения правильного указателя
            buttons_ptr = ctypes.cast(buttons, POINTER(THUMBBUTTON))
            
            hr = self.taskbar.ThumbBarAddButtons(self.hwnd, 5, buttons_ptr)
            
            if hr == 0:
                self._buttons_added = True
            
        except Exception as e:
            print(f"Ошибка добавления кнопок: {e}")
            import traceback
            traceback.print_exc()
    
    def update_play_state(self, is_playing: bool):
        """Обновляет иконку play/pause"""
        if not COMTYPES_AVAILABLE or not self._buttons_added or not self.taskbar:
            return
            
        if is_playing == self._is_playing:
            return
            
        self._is_playing = is_playing
        
        try:
            buttons = (THUMBBUTTON * 1)()
            buttons[0].dwMask = THB_ICON | THB_TOOLTIP
            buttons[0].iId = THUMBBUTTON_PLAYPAUSE
            buttons[0].hIcon = self._get_hicon('pause' if is_playing else 'play')
            buttons[0].szTip = tr('taskbar.pause') if is_playing else tr('taskbar.play')
            
            buttons_ptr = ctypes.cast(buttons, POINTER(THUMBBUTTON))
            self.taskbar.ThumbBarUpdateButtons(self.hwnd, 1, buttons_ptr)
            
        except Exception as e:
            print(f"Ошибка обновления кнопки: {e}")
