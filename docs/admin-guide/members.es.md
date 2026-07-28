# Socios

Gestión del ciclo de vida de los socios, los tipos de membresía y los grupos.

## Lista de socios

La lista permite buscar, filtrar por **estado** y por **tipo de membresía**, y paginar los
resultados. Desde ahí puedes abrir la ficha de cada socio o crear uno nuevo con **Nuevo socio**.

## Crear y editar un socio

Al dar de alta un socio se registran, entre otros datos:

- **Nombre**, **Fecha de nacimiento**, **DNI/NIE** y **Género**.
- **Tipo de membresía** (ver más abajo).
- **Notas internas** — visibles solo para administradores.

La **Fecha de alta** queda registrada automáticamente.

### Contactos

En la pestaña **Contacto** de la ficha puedes añadir varios medios de contacto (teléfono,
correo, etc.), cada uno con un **tipo** y una **etiqueta** (p. ej. «Personal», «Trabajo»). Marca
uno como **contacto principal**.

### Datos bancarios

En la ficha se registran el **IBAN** y el **BIC/SWIFT** del socio, necesarios para la
[domiciliación SEPA](sepa.es.md).

## Estados del socio

Desde la ficha puedes cambiar el estado con las acciones **Activar**, **Suspender** y
**Cancelar**. Memship **no elimina** socios de forma permanente en el flujo normal: se cancelan
para conservar el histórico.

## Tipos de membresía

Los tipos de membresía definen las categorías de socios de tu organización (p. ej. *Socio
Pleno*, *Estudiante*, *Senior*). Cada tipo tiene:

- **Nombre** y **descripción**.
- **Precio base (EUR)** y **frecuencia de facturación**.
- **Grupo** asociado (opcional).
- Restricciones de edad (opcional).

Los tipos de membresía son la base de la [generación de cuotas](payments.es.md#generar-cuotas)
y de la [facturación recurrente](settings.es.md#facturación-recurrente).

## Grupos

Los grupos permiten organizar a los socios en conjuntos (por equipo, categoría, sección…) que
luego sirven, por ejemplo, para dirigir [comunicaciones](communications.es.md) a una audiencia
concreta.

## Menores y tutores

Memship admite socios menores con un tutor asociado, para clubes con secciones infantiles o
juveniles.

## Auditoría

La pestaña **Auditoría** de la ficha muestra el registro de cambios realizados sobre ese socio.
