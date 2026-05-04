python 3.11

Numpy должен быть этой версии, иначе будут ошибки импорта
в собранном py2app приложении
numpy==1.25.2

imagecodecs только такой версии, потому что Numpy
imagecodecs==2026.1.14

!!! Установи перед тем, как устанавливать остальное
pip install aggdraw --prefer-binary

если возникает ошибка ModuleNotFoundError imp
обнови pyobjc и py2app