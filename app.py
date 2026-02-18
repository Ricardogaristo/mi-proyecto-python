import json
import os

ARCHIVO = "tareas.json"


def cargar_tareas():
    if os.path.exists(ARCHIVO):
        with open(ARCHIVO, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def guardar_tareas(tareas):
    with open(ARCHIVO, "w", encoding="utf-8") as f:
        json.dump(tareas, f, indent=4, ensure_ascii=False)


def mostrar_tareas(tareas):
    if not tareas:
        print("\nNo hay tareas registradas.\n")
        return

    print("\nLista de tareas:")
    for i, tarea in enumerate(tareas):
        estado = "✔" if tarea["completada"] else "✘"
        print(f"{i + 1}. [{estado}] {tarea['descripcion']}")
    print()


def agregar_tarea(tareas):
    descripcion = input("Descripción de la tarea: ")
    tareas.append({"descripcion": descripcion, "completada": False})
    guardar_tareas(tareas)
    print("Tarea agregada.\n")


def completar_tarea(tareas):
    mostrar_tareas(tareas)
    try:
        indice = int(input("Número de tarea a completar: ")) - 1
        tareas[indice]["completada"] = True
        guardar_tareas(tareas)
        print("Tarea marcada como completada.\n")
    except (ValueError, IndexError):
        print("Número inválido.\n")


def eliminar_tarea(tareas):
    mostrar_tareas(tareas)
    try:
        indice = int(input("Número de tarea a eliminar: ")) - 1
        tareas.pop(indice)
        guardar_tareas(tareas)
        print("Tarea eliminada.\n")
    except (ValueError, IndexError):
        print("Número inválido.\n")


def menu():
    tareas = cargar_tareas()

    while True:
        print("=== GESTOR DE TAREAS ===")
        print("1. Ver tareas")
        print("2. Agregar tarea")
        print("3. Completar tarea")
        print("4. Eliminar tarea")
        print("5. Salir")

        opcion = input("Seleccione una opción: ")

        if opcion == "1":
            mostrar_tareas(tareas)
        elif opcion == "2":
            agregar_tarea(tareas)
        elif opcion == "3":
            completar_tarea(tareas)
        elif opcion == "4":
            eliminar_tarea(tareas)
        elif opcion == "5":
            print("Saliendo...")
            break
        else:
            print("Opción inválida.\n")


if __name__ == "__main__":
    menu()
