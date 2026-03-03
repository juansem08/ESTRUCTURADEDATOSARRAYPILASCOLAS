import streamlit as st

from main import SimuladorLogistica, Pedido


# ==========================================================
#   APLICACIÓN GRÁFICA (FRONTEND) CON STREAMLIT
# ==========================================================
#
# Esta interfaz gráfica reutiliza las mismas estructuras de datos
# definidas en main.py:
# - ColaPedidos  -> COLA FIFO para recepción de pedidos.
# - InventarioAlmacen -> ARREGLO para las posiciones físicas del almacén.
# - PilaCamion   -> PILA LIFO para la carga del camión.
#
# Además, implementa una lógica de optimización para cargar el camión
# en función del orden de las paradas de la ruta:
#   - Se pide al usuario que indique los destinos en el orden de visita.
#   - Se toman todos los pedidos del inventario.
#   - Se ordenan los pedidos desde la ÚLTIMA parada hasta la PRIMERA.
#   - Se apilan (PILA LIFO) en ese orden.
# Resultado: al comenzar el reparto, en la CIMA de la pila quedan
# los paquetes de la PRIMERA parada; en el FONDO, los de la ÚLTIMA.
# De esta forma, no hace falta vaciar el camión en cada parada.


def get_simulador() -> SimuladorLogistica:
    """
    Crea (una sola vez) y recupera la instancia del simulador
    conservada en el estado de sesión de Streamlit.
    """
    if "simulador" not in st.session_state:
        st.session_state["simulador"] = SimuladorLogistica()
    return st.session_state["simulador"]


def optimizar_y_cargar_camion_por_ruta(simulador: SimuladorLogistica, ruta_destinos: list[str]) -> None:
    """
    Carga automáticamente el camión usando una PILA (LIFO) optimizada
    según la ruta de entrega.

    - Se leen todos los pedidos actualmente almacenados en el ARREGLO
      del inventario.
    - Cada pedido se clasifica según la posición de su destino en la ruta.
    - Se ordenan de la última parada a la primera.
    - Se van desapilando del inventario (retirándolos) y apilando en la
      PilaCamion.
    """
    paquetes_en_inventario: list[tuple[int, Pedido]] = []
    for pos, pedido in enumerate(simulador.inventario._arreglo):
        if pedido is not None:
            paquetes_en_inventario.append((pos, pedido))

    if not paquetes_en_inventario:
        return

    def indice_en_ruta(p: Pedido) -> int:
        """
        Devuelve el índice del destino del pedido dentro de la ruta.
        Si el destino no está en la ruta, se coloca al final.
        """
        try:
            return ruta_destinos.index(p.destino)
        except ValueError:
            return len(ruta_destinos)

    # Ordenamos de la ÚLTIMA parada a la PRIMERA para que,
    # al apilar (LIFO), la primera parada quede en la CIMA.
    paquetes_en_inventario.sort(
        key=lambda tupla: indice_en_ruta(tupla[1]),
        reverse=True,
    )

    for pos, _ in paquetes_en_inventario:
        pedido = simulador.inventario.retirar_por_posicion(pos)
        if pedido is not None:
            simulador.camion.apilar(pedido)


def ui_pedidos(simulador: SimuladorLogistica) -> None:
    """
    Sección de la interfaz para gestionar la COLA de pedidos.
    """
    st.subheader("Recepción de pedidos (COLA FIFO)")

    with st.form("form_nuevo_pedido", clear_on_submit=True):
        cliente = st.text_input("Nombre del cliente")
        descripcion = st.text_input("Descripción del producto")
        categoria = st.selectbox(
            "Categoría",
            options=simulador.inventario.categorias,
        )
        destino = st.text_input("Destino / dirección")
        submitted = st.form_submit_button("Registrar pedido en COLA")

        if submitted:
            if not cliente or not descripcion or not destino:
                st.warning("Por favor, completa todos los campos.")
            else:
                # Creamos el pedido asignando un ID incremental.
                pedido = Pedido(
                    id_pedido=simulador._contador_pedidos,
                    cliente=cliente,
                    categoria=categoria,
                    descripcion=descripcion,
                    destino=destino,
                )
                simulador._contador_pedidos += 1
                simulador.cola_pedidos.encolar(pedido)
                st.success(f"Pedido registrado y encolado correctamente: {pedido}")

    st.markdown("---")
    st.write("**Pedidos pendientes en COLA (orden de llegada):**")
    pedidos_cola = simulador.cola_pedidos.ver_todos()
    if not pedidos_cola:
        st.info("No hay pedidos en la cola.")
    else:
        for p in pedidos_cola:
            st.text(str(p))

    if st.button("Procesar siguiente pedido y almacenarlo en el inventario"):
        pedido = simulador.cola_pedidos.desencolar()
        if pedido is None:
            st.warning("No hay pedidos para procesar en la cola.")
        else:
            guardado = simulador.inventario.guardar_pedido(pedido)
            if guardado:
                st.success(f"Pedido procesado y almacenado en el inventario: {pedido}")
            else:
                st.error("No hay espacio en el inventario. El pedido no pudo almacenarse.")


def ui_inventario(simulador: SimuladorLogistica) -> None:
    """
    Sección de la interfaz para visualizar y modificar el ARREGLO de inventario.
    """
    st.subheader("Inventario del almacén (ARREGLO)")

    data = []
    for pos, pedido in enumerate(simulador.inventario._arreglo):
        if pedido is None:
            data.append(
                {
                    "Posición": pos,
                    "Estado": "[VACÍO]",
                    "Cliente": "",
                    "Categoría": "",
                    "Destino": "",
                }
            )
        else:
            data.append(
                {
                    "Posición": pos,
                    "Estado": "Ocupado",
                    "Cliente": pedido.cliente,
                    "Categoría": pedido.categoria,
                    "Destino": pedido.destino,
                }
            )

    st.dataframe(data, hide_index=True, use_container_width=True)

    st.markdown("---")
    st.write("**Retirar manualmente un pedido del inventario (por posición):**")
    pos_retirar = st.number_input(
        "Posición a retirar",
        min_value=0,
        max_value=simulador.inventario.tamanio - 1,
        step=1,
        value=0,
    )
    if st.button("Retirar de inventario"):
        pedido = simulador.inventario.retirar_por_posicion(int(pos_retirar))
        if pedido is None:
            st.warning("No hay pedido en esa posición.")
        else:
            st.success(f"Pedido retirado del inventario: {pedido}")


def ui_camion(simulador: SimuladorLogistica) -> None:
    """
    Sección de la interfaz para gestionar la PILA de carga del camión.
    Incluye la lógica de optimización de la ruta de entrega.
    """
    st.subheader("Camión de reparto (PILA LIFO)")

    st.write("**Carga actual del camión (desde la próxima entrega hasta la última):**")
    pila = simulador.camion.ver_pila()
    if not pila:
        st.info("El camión está vacío.")
    else:
        for p in pila:
            st.text(str(p))

    st.markdown("---")
    st.write("**Optimizar carga del camión según la ruta de entrega**")

    # Obtenemos todos los destinos actualmente presentes en el inventario.
    destinos_disponibles = sorted(
        {
            pedido.destino
            for pedido in simulador.inventario._arreglo
            if pedido is not None
        }
    )

    if not destinos_disponibles:
        st.info("No hay pedidos en el inventario para cargar en el camión.")
    else:
        st.write(
            "Selecciona los destinos en el **orden en que serán visitados** "
            "(de la primera parada a la última). "
            "La aplicación ordenará y cargará los paquetes para que "
            "no sea necesario vaciar el camión en cada parada."
        )
        ruta = st.multiselect(
            "Ruta de entrega (orden de visita):",
            options=destinos_disponibles,
        )

        if st.button("Optimizar carga y cargar camión"):
            if not ruta:
                st.warning("Debes seleccionar al menos un destino para construir la ruta.")
            else:
                optimizar_y_cargar_camion_por_ruta(simulador, ruta)
                st.success("Camión cargado siguiendo el orden óptimo de la ruta.")

    st.markdown("---")
    st.write("**Entregar siguiente paquete (POP de la PILA):**")
    if st.button("Entregar siguiente paquete"):
        pedido = simulador.camion.desapilar()
        if pedido is None:
            st.warning("No hay paquetes en el camión.")
        else:
            st.success(f"Paquete entregado: {pedido}")


def main() -> None:
    """
    Punto de entrada de la aplicación Streamlit.
    Ejecutar con:

        streamlit run app_streamlit.py
    """
    st.set_page_config(
        page_title="Simulador de Logística (Amazon Hub)",
        layout="wide",
    )

    st.title("Simulador de Logística y Rutas de Entrega (Amazon Hub)")
    st.caption(
        "Demostración de estructuras de datos: **COLA (FIFO)** para pedidos, "
        "**ARREGLO** para inventario y **PILA (LIFO)** para la carga del camión "
        "con optimización de ruta."
    )

    simulador = get_simulador()

    tab_pedidos, tab_inventario, tab_camion = st.tabs(
        ["📦 Pedidos (COLA)", "🏬 Inventario (ARREGLO)", "🚚 Camión (PILA)"]
    )

    with tab_pedidos:
        ui_pedidos(simulador)
    with tab_inventario:
        ui_inventario(simulador)
    with tab_camion:
        ui_camion(simulador)


if __name__ == "__main__":
    main()

