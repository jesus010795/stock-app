from django.db.models import Q
from django.views.generic import ListView
from .models import Category, Product


class ProductListView(ListView):
    model = Product
    template_name = "products/product_list.html"
    context_object_name = "products"
    paginate_by = 15

    def get_queryset(self):
        queryset = Product.objects.with_category().with_stock()
        query = self.request.GET.get("q", "").strip()

        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) | Q(sku__icontains=query)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumb_title"] = "Productos"
        context["categories"] = Category.objects.active()
        context["search_query"] = self.request.GET.get("q", "").strip()
        return context
