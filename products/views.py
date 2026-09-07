from django.views.generic import ListView
from .models import Category, Product


class ProductListView(ListView):
    model = Product
    template_name = "products/product_list.html"
    context_object_name = "products"
    paginate_by = 50

    def get_queryset(self):
        return Product.objects.with_category().with_stock()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumb_title"] = "Productos"
        context["categories"] = Category.objects.active()
        return context
