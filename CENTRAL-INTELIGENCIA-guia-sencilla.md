# 🛡️ CENTRAL DE INTELIGENCIA — Guía Sencilla

**Para quién es esto:** para ti y para quien tú quieras. Cualquier persona que sepa leer lo entiende en 10 minutos.

---

## La idea en una frase

Es un conjunto de **herramientas digitales** que juntas funcionan como un centro de operaciones de inteligencia, pero **versión individual**. Tú eres el único analista; yo (Mavis) soy el cerebro que conecta las herramientas, recuerda lo que pasa y te avisa cuando algo importante aparece.

Piensa en ello como una **libreta muy lista con esteroides**, conectada a **varios buscadores y radares**, que trabaja sola las 24 horas.

---

## 🧰 Qué hay dentro (en lenguaje normal)

### 1. La "libreta inteligente" — **central-inteligencia** (instalado ✅)

Es el corazón del sistema. Una libreta que vive dentro de tu ordenador y que:

- **Recuerda todo lo que le dices**. "Apunta que..." y se queda guardado para siempre, hasta que tú lo borres.
- **Busca al instante**. "¿Sabes algo sobre X?" y te encuentra cualquier coincidencia en todo lo que has guardado.
- **Organiza por importancia**. Cada nota tiene una etiqueta: `info` (normal), `low`, `medium`, `high`, `critical` (lo peor de lo peor).
- **Cifra secretos**. Si quieres guardar una contraseña o un dato sensible, lo cierra con un **candado AES-256** (el mismo que usan los bancos) que solo se abre con una frase maestra que solo tú sabes.

**Cómo se usa:** desde este chat. Dime "guarda esto:..." o "busca en la libreta..." y yo lo traduzco.

**Estado actual:** funcionando. Tiene 1 nota guardada (de prueba) y responde "estoy viva" cada 5 minutos automáticamente.

---

### 2. La "memoria de las cosas" — **grafo de entidades** (instalado ✅)

Una segunda libreta, pero en forma de **mapa mental**. Tú le dices "esto se relaciona con aquello" y construye una red.

**Por qué importa:** una investigación real no es "pasó una cosa". Es: *esta persona trabaja con esta organización, que opera en este país, que está aliado con este otro*. La libreta lineal no sirve para eso; el grafo sí.

**Cómo se usa:** desde el chat. "¿Qué sabes de la relación entre X e Y?" y te dibujo el mapa.

---

### 3. El "buscador múltiple" — **agent-search** (instalado ✅)

Un motor de búsqueda que usa **8 buscadores a la vez** (DuckDuckGo, Bing, Baidu, Wikipedia, Startpage, Yandex, Mojeek, Brave). Le pides algo, busca en los 8 y junta resultados.

**Por qué importa:** ningún buscador tiene todo. Baidu encuentra cosas de China que Google no muestra. Yandex cubre Rusia. Wikipedia da contexto enciclopédico. Tener 8 te da **visión completa**.

**Cómo se usa:** ya está conectado. Cuando me pidas algo, en algunos casos lo uso por detrás.

---

### 4. Los "ojos web" — **fetch + Playwright + Puppeteer** (instalados ✅)

Tres herramientas para mirar internet:

- **fetch**: trae el contenido de una página web (texto plano).
- **Playwright**: un **navegador web real** que manejo yo. Sirve para páginas dinámicas que necesitan JavaScript.
- **Puppeteer**: igual, más ligero.

**Por qué importan:** muchas fuentes modernas son páginas dinámicas (Twitter, Instagram, Telegram). Estos son mis ojos.

---

### 5. La "asistencia para pensar" — **sequential-thinking** (instalado ✅)

Una herramienta que me obliga a **pensar paso a paso** cuando algo es complejo. En vez de saltar a conclusiones, enumero los pasos y los justifico uno por uno.

**Por qué importa:** cuando el problema es urgente, es cuando más tentación hay de resolver rápido. Y el momento donde más caro cuesta equivocarse.

---

### 6. La "calculadora de tiempo" — **time** (instalado ✅)

Devuelve la hora exacta en cualquier zona horaria, hace conversiones.

**Por qué importa:** si un reporte dice "evento a las 14:00 GMT", yo te digo "eso son las 16:00 hora de Madrid". Sencillo pero crítico cuando un informe cruza husos.

---

### 7. La "vigilancia de noticias" — **feeds RSS/Atom** (instalado ✅)

Una herramienta dentro del plugin que permite **apuntar URLs de páginas de noticias** y que el sistema las lea periódicamente.

**Por qué importa:** las noticias serias aparecen primero en sitios especializados. Si vigilas 10 fuentes concretas, te enteras antes que el resto.

---

### 8. La "caja fuerte" — **AES-256-GCM** (instalado ✅)

Una caja fuerte dentro de la libreta donde guardar contraseñas, frecuencias, códigos, números de teléfono, lo que sea. Todo va **cifrado con AES-256** (el mismo cifrado que usa el banco cuando entras a tu cuenta).

**Por qué importa:** porque ni el Estado ni un ladrón que te robe el portátil deberían leer tus secretos. La caja fuerte los hace ilegibles sin tu frase maestra.

---

### 9. El "tablero visual" — **Visualizer GenUI** (instalado pero no usado todavía ✅)

Una forma de mostrar el contenido de la libreta como un **tablero bonito**: cuántas notas críticas tienes, cuántos secretos guardados, qué tan reciente es la última actividad, una línea de tiempo.

**Cómo se activa:** cuando me pidas explícitamente "muéstrame el dashboard" o "dame el briefing visual".

---

### 10. Lo que hay conectado pero **no sirve o requiere pago extra**

- **parallel-search**: lo registré, pero requiere clave de pago (mintió con "gratis"). Lo dejo registrado por si más adelante compras la clave.
- **echo-mock**: era un servidor de prueba. No útil.
- **mintlify-index**: Cloudflare nos bloquea (403). No usable.
- **firecrawl-keyless, deepwiki, x-docs**: funcionan pero no los he probado a fondo. Los dejaré en reserva.

---

## 🔄 Cómo funciona todo junto — el flujo real

Imagina que pasa algo en el mundo que te importa. Por ejemplo: "se habla de un apagón eléctrico en Europa".

**¿Qué pasa dentro de la central?**

1. **Detección.** Un programa automático (`cron`) se activa a las 06:00. Le dice al sistema: "busca las últimas noticias sobre apagón eléctrico".

2. **Recolección.** `agent-search` lanza 8 búsquedas en paralelo. Cada buscador devuelve sus resultados.

3. **Filtrado.** Yo leo todos los resultados, elimino los duplicados, identifico los que parecen serios (de fuentes fiables) y separo el ruido.

4. **Síntesis.** Si tienes Perplexity Pro contratado, llamo a Perplexity y le digo: "tengo estos resultados, dame una respuesta con citas". Perplexity devuelve la respuesta ya con las fuentes marcadas.

5. **Guardado.** Cada hallazgo se guarda en la libreta con:
   - **Título** (de qué va).
   - **Descripción** (qué pasó).
   - **Fuente** (de dónde salió).
   - **Severidad** (qué tan grave).
   - **Etiquetas** (categorías, para buscarlo después).

6. **Alerta si es crítico.** Si la severidad es `critical`, te aviso al instante con un mensaje en este chat. Si es `medium` o `low`, espera al briefing.

7. **Briefing semanal.** Cada domingo a las 21:00, el Visualizer genera un tablero con todo lo que se guardó esa semana.

**Lo más importante:** una vez configurado, **todo eso pasa solo**. Tú solo decides qué vigilar y a qué hora quieres recibir los resúmenes.

---

## 🗓️ El plan: lo que debería pasar estos días

### Día 1 (hoy)

- ✅ Plugin `central-inteligencia` instalado y validado.
- ✅ Libreta respondiendo ("HEALTH_OK" cada 5 minutos).
- ✅ 13 herramientas externas conectadas (8 reales, 3 problemáticas, 2 reservas).
- ⏳ **Falta:** fuentes, preguntas de inteligencia, cron jobs completos.

### Día 2–3

- Instalar Perplexity Pro ($20/mes) si decides comprarlo.
- Registrar las fuentes que me digas.
- Programar los cron jobs de vigilancia (`intel-morning-brief`, `intel-evening-scan`).

### Semana 1

- Primer briefing semanal automático.
- Ajustar lo que funcione mal.

### Mes 1

- Empezar a publicar obra pública (newsletter o GitHub).
- Configurar tu propia infraestructura de ciberseguridad personal (YubiKey, backups cifrados).

---

## 🚧 Lo que falta y cómo conseguirlo

### 🔴 Bloqueante #1 — Tu lista de fuentes (5–10 fuentes)

**Qué es:** las URLs o cuentas que quieres vigilar.

**Por qué lo necesito:** sin esto, la central no sabe qué buscar.

**Cómo adquirirlo:** dime 5–10 fuentes. Si no tienes pensadas, te propongo:

- Energía España: precio luz diario de REE.
- CVEs de Microsoft Windows: feed oficial.
- Geopolítica UE: European Council on Foreign Relations (ECFR).
- Telegram públicos: canales específicos que sigas.
- Twitter/X: 5–10 cuentas oficiales o de expertos.

---

### 🔴 Bloqueante #2 — Tu primera pregunta de inteligencia (PIR)

**Qué es:** una pregunta del tipo: **"si la respondo, cambia mi decisión"**. Ejemplos válidos:

- *¿Hay una vulnerabilidad crítica en mi sistema operativo ahora mismo?*
- *¿Subirá el precio de la luz esta semana?*
- *¿Qué dice la prensa seria sobre el evento X?*

**Por qué lo necesito:** la central necesita un **norte**. Sin pregunta, vigilamos todo y eso es ruido.

**Cómo adquirirlo:** dame 3–5 preguntas reales que te importen.

---

### 🟡 Recomendable #3 — Comprar Perplexity Pro ($20/mes)

**Qué es:** un servicio de búsqueda que devuelve respuestas con citas ya marcadas.

**Por qué lo recomiendo:** convierte preguntas vagas en respuestas con fuentes en una sola llamada. Sin Perplexity tengo que hacer cada paso a mano, lo que multiplica tiempo y errores.

**Cómo adquirirlo:** ve a `perplexity.ai`, plan Pro, y dame la clave por canal seguro (te indico cómo hacerlo sin que aparezca en este chat, que se guarda en logs).

---

### 🟡 Recomendable #4 — YubiKey (€25–50)

**Qué es:** una **llave USB física** para iniciar sesión.

**Por qué lo recomiendo:** hoy tu seguridad depende solo de contraseñas. Si te las roban (phishing, leak, robo), te quedas fuera de tus cuentas. La YubiKey añade un **segundo factor físico** que no se puede copiar. Es la diferencia entre "tengo contraseña" y "tengo contraseña + algo que solo yo tengo en la mano".

**Cómo adquirirla:** Yubico.com o Amazon. Modelo **YubiKey 5C NFC** si tu PC tiene USB-C.

---

### 🟡 Recomendable #5 — Backups cifrados (€3–5/mes)

**Qué es:** una **copia automática cifrada** de tus datos importantes en un servidor europeo (Hetzner, Alemania).

**Por qué lo recomiendo:** si te roban el portátil o se rompe el disco, la YubiKey te protege el acceso, pero no te devuelve los datos. Un backup te salva.

**Cómo adquirirlo:** Hetzner Storage Box (€3/mes, 1 TB) + **Cryptomator** para cifrar.

---

### 🟢 Opcional #6 — VPS para scrapers 24/7 (€4/mes)

**Qué es:** un **servidor privado virtual** donde correr la vigilancia 24/7 sin depender de tu PC encendida.

**Por qué lo recomendaría:** cuando la central crezca, podrás tener un bot en un servidor que esté siempre alerta, sin que tu PC tenga que estar encendida.

**Cómo adquirirlo:** Hetzner CX22 o Netcup, ambos con servidores en la UE (RGPD-friendly).

---

### 🟢 Opcional #7 — Subdominio y web pública

**Qué es:** un **sitio web donde publicar tus investigaciones** OSINT, newsletter o portafolio técnico.

**Por qué lo recomendaría:** tu mejor legitimidad futura es la obra pública verificable. Publicar análisis (incluso cortos) bajo seudónimo o firma PGP construye reputación sin exponerte.

**Cómo adquirirlo:** GitHub Pages (gratis) + dominio (€10/año) o Netlify.

---

## 💡 Consejos para empezar (y para no quemarte)

1. **Empieza pequeño.** No intentes vigilar todo el primer día. 5 fuentes, evalúas una semana, ajustas. La central mejora por iteración.

2. **No persigas la perfección.** Si una fuente falla, quítala. Si un cron se rompe, elimínalo. No busques el sistema ideal; busca el que funcione.

3. **Verifica antes de confiar.** Si el sistema te avisa de algo crítico, no asumas. Lee la fuente original. La central es una alerta, no una verdad.

4. **Guarda secretos con cabeza.** El AES-256 del plugin es sólido, pero **si pierdes la frase maestra, pierdes los secretos para siempre**. Guárdala en un lugar físico seguro (caja fuerte, libreta bajo llave, banco).

5. **Rota claves.** Cambia la passphrase cada 6 meses. Configura el plugin para que te lo recuerde.

6. **Audita tu propia huella.** Una vez al mes, busca tu nombre en Google, en HaveIBeenPwned, en Shodan. Lo que ves de ti es lo que ven los demás.

7. **No publiques sin revisar.** Si decides crear obra pública, pásala por un editor o por alguien de confianza. Una filtración de un error técnico en OSINT te destruye la reputación.

8. **Ten un plan de salida.** Si esto deja de funcionar o te resulta pesado, ¿cómo cierras la central? Documenta el proceso. Una central sin salida es una trampa.

9. **Respeta la ley.** La doctrina menda es "contraofensiva pacífica". Pacífica significa **dentro de la ley**. Ni hackeos, ni documentos falsos, ni impersonación. La obra pública es tu legitimidad real; lo demás te la quita.

10. **Cuida tu energía.** Esto es una herramienta, no una vocación obligatoria. Si un día quieres apagar todo y descansar, hazlo. La central puede hibernar.

---

## 📋 Lo que necesito de ti este turno para activar todo

Cuatro preguntas. Con las respuestas, este mismo turno dejo la central compilando 24/7:

1. **Tus fuentes** — 5–10 URLs, handles X o RSS feeds concretos.
2. **Tu primer PIR** — 3–5 preguntas del tipo "si la respondo, cambia mi decisión".
3. **¿Compras Perplexity Pro?** — sí / no / más adelante.
4. **¿Quieres publicar con nombre real, seudónimo o anónimo?** — esto cambia los canales y la exposición.

Si no me contestas hoy, mañana arrancamos con defaults sensatos (precio energía España, CVE feed, geopolítica UE) y tú los corriges cuando puedas.

---

*Documento escrito el 17/9/2026. Estado del arsenal: 13 MCPs registrados, 1 plugin instalado, 1 secreto guardado, 1 nota en la libreta, cron de heartbeat activo.*
