@echo off
rem Lanzado por iniciar.cmd en una ventana minimizada con el titulo
rem "webllm-puente". Vive en su propio fichero para que "start" solo
rem tenga que abrir UNA ruta entre comillas, en vez de mezclar en la
rem misma linea un titulo, el modificador /d y un comando de varias
rem palabras -- esa mezcla es la que hacia que Windows intentase abrir
rem un "fichero" llamado literalmente "webllm-puente" y fallase con
rem "Windows no puede encontrar el archivo 'webllm-puente'".
cd /d "%~dp0"
python -m webllm_agent.cli.main puente
