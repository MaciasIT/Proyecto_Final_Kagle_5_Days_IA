Claro, aquí está el documento técnico profesional basado en los hechos proporcionados.

***

# Guía de Uso de los Comandos `ls` y `mkdir` en Linux

## Resumen Ejecutivo

Este documento detalla el procedimiento para listar el contenido de un directorio y crear nuevos directorios utilizando la línea de comandos en un entorno Linux (Ubuntu). Se demuestran las funcionalidades básicas del comando `ls` con las opciones `-l` (formato largo) y `-a` (mostrar archivos ocultos), así como el uso del comando `mkdir` para la creación de un nuevo directorio, verificando su resultado.

## Prerrequisitos

*   Acceso a una terminal de línea de comandos en un sistema operativo basado en Linux, como Ubuntu.
*   Permisos de usuario para crear archivos y directorios en el directorio de trabajo actual.

## Procedimiento Paso a Paso

1.  **Identificar el Entorno de Trabajo**
    Al iniciar la sesión en la terminal, el prompt muestra información sobre el usuario (`user`), el nombre del host (`ubuntu`) y el directorio actual (`~`, que representa el directorio `home` del usuario).

    ```bash
    user@ubuntu:~$
    ```

2.  **Listar Contenido Básico del Directorio**
    Ejecute el comando `ls` para obtener una lista simple de los archivos y directorios no ocultos.

    ```bash
    user@ubuntu:~$ ls
    ```

    **Salida esperada:**
    ```
    Desktop  Documents  Downloads  Music  Pictures  Public  Templates  Videos
    ```

3.  **Obtener un Listado Detallado**
    Utilice la opción `-l` para mostrar el contenido en formato largo. Esta vista incluye permisos, número de enlaces, propietario, grupo, tamaño, y fecha de última modificación.

    ```bash
    user@ubuntu:~$ ls -l
    ```

    **Salida esperada:**
    ```
    drwxr-xr-x 2 user user 4096 Jun 15 10:23 Desktop
    drwxr-xr-x 2 user user 4096 Jun 15 10:23 Documents
    drwxr-xr-x 2 user user 4096 Jun 15 10:23 Downloads
    drwxr-xr-x 2 user user 4096 Jun 15 10:23 Music
    drwxr-xr-x 2 user user 4096 Jun 15 10:23 Pictures
    drwxr-xr-x 2 user user 4096 Jun 15 10:23 Public
    drwxr-xr-x 2 user user 4096 Jun 15 10:23 Templates
    drwxr-xr-x 2 user user 4096 Jun 15 10:23 Videos
    ```

4.  **Mostrar Archivos y Directorios Ocultos**
    Ejecute `ls` con la opción `-a` para listar todos los archivos, incluyendo los ocultos (aquellos cuyos nombres comienzan con un punto).

    ```bash
    user@ubuntu:~$ ls -a
    ```

    **Salida esperada:**
    ```
    .  ..  .bash_history  .bash_logout  .bashrc  Desktop  Documents  Downloads  Music  .profile  Pictures  Public  .ssh  Templates  Videos
    ```

5.  **Crear un Nuevo Directorio**
    Utilice el comando `mkdir` seguido del nombre deseado para crear un nuevo directorio. Si la operación es exitosa, el comando no devolverá ninguna salida.

    ```bash
    user@ubuntu:~$ mkdir test_dir
    ```

6.  **Verificar la Creación del Directorio**
    Ejecute el comando `ls` nuevamente para confirmar que el directorio `test_dir` ha sido creado correctamente.

    ```bash
    user@ubuntu:~$ ls
    ```

    **Salida esperada:**
    ```
    Desktop  Documents  Downloads  Music  Pictures  Public  Templates  test_dir  Videos
    ```

## Solución de Problemas

*   **Error "File exists" al usar `mkdir`**: Si al ejecutar `mkdir nombre_directorio` se recibe el mensaje `mkdir: cannot create directory ‘nombre_directorio’: File exists`, significa que ya existe un archivo o directorio con ese mismo nombre en la ubicación actual. Verifique el nombre y elija uno que no esté en uso.
*   **Error "Permission denied"**: Si recibe un error de permisos denegados, significa que su usuario actual no tiene los privilegios necesarios para crear directorios en la ubicación seleccionada. Intente ejecutar el comando en su directorio `home` (`~`) o contacte al administrador del sistema.
