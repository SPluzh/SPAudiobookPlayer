"""
Module for displaying progress on the Windows taskbar button
Requires: pip install comtypes
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
        print("comtypes is not installed. Install it with: pip install comtypes")


if COMTYPES_AVAILABLE:
    # Define ITaskbarList3 interface using comtypes
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

    # Structure for thumbnail toolbar buttons
    class THUMBBUTTON(ctypes.Structure):
        _fields_ = [
            ('dwMask', ctypes.c_uint),
            ('iId', ctypes.c_uint),
            ('iBitmap', ctypes.c_uint),
            ('hIcon', ctypes.c_void_p),
            ('szTip', ctypes.c_wchar * 260),
            ('dwFlags', ctypes.c_uint),
        ]

    # Thumbnail button constants
    THB_BITMAP = 0x1
    THB_ICON = 0x2
    THB_TOOLTIP = 0x4
    THB_FLAGS = 0x8
    
    THBF_ENABLED = 0x0
    THBF_DISABLED = 0x1
    THBF_DISMISSONCLICK = 0x2
    THBF_NOBACKGROUND = 0x4
    THBF_HIDDEN = 0x8
    
    # Custom button IDs
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

    # TaskbarList CLSID
    CLSID_TaskbarList = GUID('{56FDF344-FD6D-11d0-958A-006097C9A090}')


class TaskbarProgress:
    """Manages progress bar display on the Windows taskbar button"""
    
    # Progress states
    TBPF_NOPROGRESS = 0x0
    TBPF_INDETERMINATE = 0x1
    TBPF_NORMAL = 0x2
    TBPF_ERROR = 0x4
    TBPF_PAUSED = 0x8
    
    def __init__(self):
        """Initialize taskbar interface"""
        self.hwnd = None
        self.taskbar = None
        self._initialized = False
        self._current_state = self.TBPF_NOPROGRESS
        
        if sys.platform == 'win32' and COMTYPES_AVAILABLE:
            self._init_taskbar()
    
    def _init_taskbar(self):
        """Internal initialization of the COM interface"""
        try:
            taskbar = comtypes.client.CreateObject(
                CLSID_TaskbarList,
                interface=ITaskbarList3
            )
            
            taskbar.HrInit()
            
            self.taskbar = taskbar
            self._initialized = True
            
        except Exception as e:
            print(f"Failed to initialize TaskbarProgress: {e}")
            self._initialized = False
    
    @property
    def is_available(self) -> bool:
        """Check if taskbar functionality is available for current window"""
        return self._initialized and self.hwnd is not None
    
    def set_hwnd(self, hwnd: int):
        """Register the window handle for taskbar updates"""
        self.hwnd = hwnd
    
    def set_progress(self, current: float, total: float):
        """Set numerical progress value"""
        if not self.is_available:
            return
        
        try:
            # Convert to integers for API
            current_int = max(0, int(current))
            total_int = max(1, int(total))
            
            self.taskbar.SetProgressValue(self.hwnd, current_int, total_int)
            
        except Exception:
            pass
    
    def set_progress_percent(self, percent: int):
        """Set progress as percentage (0-100)"""
        self.set_progress(percent, 100)
    
    def set_state(self, state: int):
        """Set progress bar visual state (normal, paused, error, etc.)"""
        if not self.is_available:
            return
        
        try:
            self.taskbar.SetProgressState(self.hwnd, state)
            self._current_state = state
        except Exception:
            pass
    
    def set_normal(self):
        """Set progress bar to normal (green) state"""
        self.set_state(self.TBPF_NORMAL)
    
    def set_paused(self):
        """Set progress bar to paused (yellow) state"""
        self.set_state(self.TBPF_PAUSED)
    
    def set_error(self):
        """Set progress bar to error (red) state"""
        self.set_state(self.TBPF_ERROR)
    
    def set_indeterminate(self):
        """Set progress bar to indeterminate (pulsing) state"""
        self.set_state(self.TBPF_INDETERMINATE)
    
    def clear(self):
        """Hide the progress bar from the taskbar button"""
        self.set_state(self.TBPF_NOPROGRESS)
    
    def update_for_playback(self, is_playing: bool, current: float, total: float):
        """Sync taskbar progress and state with playback status"""
        if not self.is_available:
            return
        
        # Set state based on playing status
        new_state = self.TBPF_NORMAL if is_playing else self.TBPF_PAUSED
        
        if new_state != self._current_state:
            self.set_state(new_state)
        
        self.set_progress(current, total)


class TaskbarThumbnailButtons:
    """Manages playback control buttons in the Windows taskbar thumbnail preview"""
    
    def __init__(self, taskbar_interface, hwnd: int, icons_dir):
        """Initialize thumbnail buttons with taskbar interface and window handle"""
        self.taskbar = taskbar_interface
        self.hwnd = hwnd
        self.icons_dir = icons_dir
        self._buttons_added = False
        self._is_playing = False
        self._buttons_cache = None  # Cache buttons array to prevent GC collection
        
    def _get_hicon(self, name: str):
        """Load icon file and return Windows HICON handle"""
        # Try Loading ICO first
        ico_path = self.icons_dir / f"{name}.ico"
        if ico_path.exists():
            return ctypes.windll.user32.LoadImageW(
                0, str(ico_path), 1, 64, 64, 0x10
            )
        
        # Fallback to PNG (limited support via LoadImageW)
        png_path = self.icons_dir / f"{name}.png"
        if png_path.exists():
            return ctypes.windll.user32.LoadImageW(
                0, str(png_path), 1, 64, 64, 0x10
            )
            
        return None

    def add_buttons(self):
        """Add playback control buttons to the thumbnail toolbar"""
        if not COMTYPES_AVAILABLE or not self.taskbar or self._buttons_added:
            return
            
        try:
            buttons = (THUMBBUTTON * 5)()
            self._buttons_cache = buttons
            
            # 1. Previous Button
            buttons[0].dwMask = THB_ICON | THB_TOOLTIP | THB_FLAGS
            buttons[0].iId = THUMBBUTTON_PREV
            buttons[0].hIcon = self._get_hicon('prev')
            buttons[0].szTip = tr('taskbar.prev')
            buttons[0].dwFlags = THBF_ENABLED
            
            # 2. Rewind Button
            buttons[1].dwMask = THB_ICON | THB_TOOLTIP | THB_FLAGS
            buttons[1].iId = THUMBBUTTON_REWIND
            buttons[1].hIcon = self._get_hicon('rewind_10')
            buttons[1].szTip = tr('taskbar.rewind')
            buttons[1].dwFlags = THBF_ENABLED
            
            # 3. Play/Pause Button
            buttons[2].dwMask = THB_ICON | THB_TOOLTIP | THB_FLAGS
            buttons[2].iId = THUMBBUTTON_PLAYPAUSE
            buttons[2].hIcon = self._get_hicon('play')
            buttons[2].szTip = tr('taskbar.play')
            buttons[2].dwFlags = THBF_ENABLED
            
            # 4. Forward Button
            buttons[3].dwMask = THB_ICON | THB_TOOLTIP | THB_FLAGS
            buttons[3].iId = THUMBBUTTON_FORWARD
            buttons[3].hIcon = self._get_hicon('forward_10')
            buttons[3].szTip = tr('taskbar.forward')
            buttons[3].dwFlags = THBF_ENABLED
            
            # 5. Next Button
            buttons[4].dwMask = THB_ICON | THB_TOOLTIP | THB_FLAGS
            buttons[4].iId = THUMBBUTTON_NEXT
            buttons[4].hIcon = self._get_hicon('next')
            buttons[4].szTip = tr('taskbar.next')
            buttons[4].dwFlags = THBF_ENABLED
            
            buttons_ptr = ctypes.cast(buttons, POINTER(THUMBBUTTON))
            
            hr = self.taskbar.ThumbBarAddButtons(self.hwnd, 5, buttons_ptr)
            
            if hr == 0:
                self._buttons_added = True
            
        except Exception as e:
            print(f"Error adding thumbnail buttons: {e}")
            import traceback
            traceback.print_exc()
    
    def update_play_state(self, is_playing: bool):
        """Update the central play/pause button icon and tooltip"""
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
            print(f"Error updating thumbnail button: {e}")
