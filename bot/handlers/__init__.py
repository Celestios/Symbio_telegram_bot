from .main_menu import *
from .profile_edit import *
from .content import *
from .settings import *
from bot.register import register

__all__ = (
    main_menu.__all__ +
    content.__all__ +
    profile_edit.__all__ +
    settings.__all__ +
    [register]
)