/* ===========================================================
   AlmacenSys — product-autocomplete.js
   Autocompletado en tiempo real del campo producto del formulario
   de movimientos (/movimientos/nuevo/).

   Marcaje esperado (movimiento_form.html):
   <div class="autocomplete" data-autocomplete
        data-autocomplete-url="{% url 'inventory:buscar-productos' %}">
     <input ... data-autocomplete-input data-autocomplete-hidden="id_product">
     <button ... data-autocomplete-clear>
     <ul ... data-autocomplete-list>
   </div>

   El input visible NO es parte del form: el pk elegido se escribe en
   el campo oculto `id_product` y el servidor valida como siempre.
   JS puro, sin dependencias. Con la lista abierta, Enter elige la
   opción resaltada (o la primera) y no envía el formulario; Tab la cierra.
   =========================================================== */

(function () {
  "use strict";

  var MIN_LENGTH = 2;
  var DEBOUNCE_MS = 250;

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-autocomplete]").forEach(initAutocomplete);
  });

  function initAutocomplete(widget) {
    var url = widget.getAttribute("data-autocomplete-url");
    var input = widget.querySelector("[data-autocomplete-input]");
    var hidden = document.getElementById(
      input.getAttribute("data-autocomplete-hidden")
    );
    var list = widget.querySelector("[data-autocomplete-list]");
    var clearButton = widget.querySelector("[data-autocomplete-clear]");
    var debounceTimer = null;
    var inFlight = null;
    var activeIndex = -1;

    function options() {
      return list.querySelectorAll(".autocomplete-option");
    }

    function closeList() {
      list.hidden = true;
      list.innerHTML = "";
      activeIndex = -1;
      input.setAttribute("aria-expanded", "false");
    }

    function setSelected(id, label) {
      hidden.value = id ? String(id) : "";
      input.value = label || "";
      clearButton.hidden = !id;
      closeList();
    }

    // Misma ruta para el mouse y para Enter. No usar .click(): el
    // listener del botón es mousedown, y click() no lo dispara.
    function chooseOption(option) {
      setSelected(option.getAttribute("data-id"), option.textContent);
    }

    function renderResults(items) {
      list.innerHTML = "";
      activeIndex = -1;

      if (!items.length) {
        var empty = document.createElement("li");
        empty.className = "autocomplete-empty";
        empty.textContent = "Sin resultados";
        list.appendChild(empty);
        list.hidden = false;
        return;
      }

      items.forEach(function (item) {
        var li = document.createElement("li");
        li.setAttribute("role", "option");
        var button = document.createElement("button");
        button.type = "button";
        button.className = "autocomplete-option";
        button.setAttribute("data-id", item.id);
        button.textContent = item.label;
        // mousedown + preventDefault: el input no pierde el foco antes
        // de que el click llegue, así no hay carrera con el cierre.
        button.addEventListener("mousedown", function (event) {
          event.preventDefault();
          chooseOption(button);
        });
        li.appendChild(button);
        list.appendChild(li);
      });

      list.hidden = false;
      input.setAttribute("aria-expanded", "true");
    }

    function fetchJson(query) {
      if (inFlight) inFlight.abort();
      inFlight = new AbortController();
      fetch(
        url + "?q=" + encodeURIComponent(query),
        { credentials: "same-origin", signal: inFlight.signal }
      )
        .then(function (response) {
          if (!response.ok) throw new Error("HTTP " + response.status);
          return response.json();
        })
        .then(function (data) {
          renderResults(data.results || []);
        })
        .catch(function (error) {
          // AbortError = llegó una tecla más nueva: no es un fallo.
          if (error.name !== "AbortError") closeList();
        });
    }

    function moveActive(step) {
      var items = options();
      if (!items.length) return;
      activeIndex = (activeIndex + step + items.length) % items.length;
      items.forEach(function (element, index) {
        element.classList.toggle("active", index === activeIndex);
      });
      items[activeIndex].scrollIntoView({ block: "nearest" });
    }

    input.addEventListener("input", function () {
      // Editar el texto descarta la selección anterior: el hidden se
      // limpia y el servidor valida solo lo que vuelva a elegirse.
      hidden.value = "";
      clearButton.hidden = true;

      var query = input.value.trim();
      if (query.length < MIN_LENGTH) {
        clearTimeout(debounceTimer);
        closeList();
        return;
      }
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(function () {
        fetchJson(query);
      }, DEBOUNCE_MS);
    });

    input.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        closeList();
        return;
      }
      // Tab mueve el foco: la lista no debe quedarse abierta.
      if (event.key === "Tab") {
        closeList();
        return;
      }
      if (list.hidden) return;
      if (event.key === "Enter") {
        event.preventDefault();
        var items = options();
        if (!items.length) return;
        chooseOption(items[activeIndex >= 0 ? activeIndex : 0]);
        return;
      }
      if (!options().length) return;
      if (event.key === "ArrowDown") {
        event.preventDefault();
        moveActive(1);
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        moveActive(-1);
      }
    });

    document.addEventListener("click", function (event) {
      if (!widget.contains(event.target)) closeList();
    });

    clearButton.addEventListener("click", function () {
      setSelected("", "");
      input.focus();
    });

    // Prefijado: si el hidden trae pk (?producto= o re-render con
    // errores), pide la etiqueta al endpoint para pintarla en el input.
    // Si el usuario escribió o limpió antes de que llegue la respuesta,
    // no se pisa el texto.
    var prefillId = hidden.value;
    if (prefillId) {
      fetch(
        url + "?id=" + encodeURIComponent(prefillId),
        { credentials: "same-origin" }
      )
        .then(function (response) {
          if (!response.ok) throw new Error("HTTP " + response.status);
          return response.json();
        })
        .then(function (data) {
          if (hidden.value !== prefillId || input.value) return;
          var item = (data.results || [])[0];
          if (item) setSelected(item.id, item.label);
        })
        .catch(function () {
          /* Se deja el hidden tal cual: el form lo valida. */
        });
    }
  }
})();
