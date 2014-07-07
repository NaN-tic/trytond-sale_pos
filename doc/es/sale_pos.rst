==========
Ventas TPV
==========

Configuración
=============

Desde el menú Ventas/Configuración/Tiendas se definen las tiendas físicas donde
se harán las ventas TPV, indicando la secuencia de las ventas (pedidos), el
almacén desde donde se envían/reciben los productos y la tarifa, plazo de pago,
tercero por defecto y si se desea que por defecto se cree albarán para entregar
los productos vendidos en el domicilio del cliente, o éste se los lleva en el
momento de la venta.

Desde el menú Ventas/Configuración/Dispositivos se definen los dispositivos
físicos (terminales de venta) de cada tienda. Cada dispositivo tiene un nombre,
pertenece a una tienda y tiene asociados uno o varios diarios de extractos
contables (donde se anotarán los pagos). También se puede definir uno de estos
diarios de extractos que sea el usado por defecto en los pagos, normalmente el
más utilizado. Por ejemplo un dispositivo "TPV001" puede tener asociado los
diarios de extractos "Efectivo-TPV001" y "Tarjeta-TPV001". Y si és más habitual
recibir los pagos en efectivo, definir "Efectivo-TPV001" como el diario de
extractos por defecto.

Venta
=====

Para gestionar las ventas TPV accederemos al menú Ventas/Ventas TPV.

Una venta TPV es una venta simplificada: está compuesta principalmente por una
parte en la que se define los datos de la venta (a la derecha) y otra parte
compuesta de líneas de venta en la que se definen los productos, sus cantidades
y precios (a la izquierda).

Primero hay que seleccionar el cliente, si no se usa un cliente genérico
definido como el tercero por defecto de la tienda. Posteriormente podemos añadir
líneas en la venta TPV de dos formas distintas:

* Mediante la introducción directa de las líneas por ser una lista editable tipo
  hoja de cálculo. Puede escanearse el producto o introducir su código o nombre,
  luego pulsar la tecla Enter, introducir la cantidad y volver a pulsar la tecla
  Enter para saltar a una línea nueva. También se pueden usar las teclas Tab y
  Mayús+Tab para saltar al campo siguiente/anterior.
* Mediante el botón "Añadir producto" que permite introducir los mismos datos en
  una ventana emergente.

Es posible añadir subtotales a la venta con el botón "Añadir suma".

En las líneas de venta TPV también se muestran el precio unidad con impuestos y
el total con impuestos.

En la parte derecha se muestra los importes base, impuestos y total de la venta,
así como el importe pagado y el pendiente.

Pagar una venta
===============

Mediante el botón "Pagar" se procede al pago total o parcial de una venta. En
una ventana emergente se pide el diario de extracto (forma de pago) y el importe
a pagar (por defecto el pendiente). Se puede realizar pagos parciales con la
misma o distintas formas de pago, por ejemplo sólo con Efectivo o con Efectivo y
Tarjeta. También se puede indicar un importe mayor que el de la venta, para que
aparezca un importe negativo indicando el cambio a devolver. Es importante que
se haya creado previamente un extracto bancario borrador donde anotar los pagos,
si no el programa nos avisará.

Si se realiza un pago parcial, se volverá a mostrar la ventana emergente con el
nuevo importe pendiente. Siempre se puede cancelar el nuevo pago, de forma que
la venta quedaría parcialmente pagada (por ejemplo cuando se hace una reserva
con una paga y señal).

Si se realiza un pago completo o el último pago parcial (el importe pendiente es
cero), la ventana emergente desaparece, la venta se confirma y se crean los
albaranes para el envío/recepción de productos y las facturas/abonos para la
contabilización de la venta. (todo: También se imprime el ticket de la venta TPV):

* Si la venta TPV tiene sólo cantidades positivas, se crea un albarán de envío y
  una factura de cliente.
* Si la venta tiene sólo cantidades negativas (devolución), se crea un albarán
  de devolución y un abono de cliente.
* Si la venta tiene cantidades positivas y negativas, se crea ambos albaranes y
  facturas: Un albarán de envío y un albarán de devolución y una factura de
  cliente y un abono de cliente.

Las facturas/abonos quedan en estado confirmados (contabilizados), de forma que
es posible imprimir la factura en lugar del tiquet de la venta TPV. Los
albaranes quedan confirmados, reservados y realizados, pues una venta TPV
implica que los productos son transportados por el propio cliente en el momento
de la venta.

Pueden consultarse los pagos y las facturas asociadas a la venta TPV en las
pestañas "Pagos" y "Facturas".

Autorecogida
============

Una venta TPV por defecto no genera albaranes. Sólo genera los movimientos de stock.

Si al procesar un pedido de venta desea que genere los albaranes, debe desmarcar en
el pedido de venta la opción "Autorecogida".

A la configuración de la tienda puede configurar si la opción de "Autorecogida"
se activa o no cada vez que genere un nuevo pedido de venta. Si a la tienda desmarca
la opción "Autorecogida", cuando genere un pedido estará desmarcado el campo "Autorecogida"
y generá el albarán y sus movimientos.

Los pedidos o ventas que el cliente se lleva en el momento la mercadería no hace falta
generar albaranes, pues no se realizará una entrega posterior y no hace falta generar
un albarán.

Estados
=======

Las ventas TPV cambian entre los siguientes estados:

* Borrador a En proceso, cuando se paga completamente la venta TPV.
* En proceo a Realizada, cuando se realiza el cierre de caja y las facturas
  asociadas a la venta TPV quedan pagadas.

Cuando se realiza la validación y confirmación de los extractos contables las
facturas asociadas quedan pagadas y las ventas TPV realizadas. En algunos casos,
por ejemplo cuando existen pagos parciales negativos o ventas TPV con facturas y
abonos a la vez, las facturas no quedan pagadas automáticamente y hay que
ejecutar el asistente de cierre de ventas TPV (todo) para que las facturas
queden pagadas y las ventas TPV realizadas.

.. note::  Se generan albaranes sólo si hay al menos una línea del pedido de
           venta relacionada con un producto que sea de tipo Bienes.

Informes
========

Desde las ventas TPV hay 3 informes:

* Ticket de venta
* Resumen de ventas
* Resumen de ventas por tercero
